# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import inspect
from typing import Any, Callable, Dict, Optional, Union
from kfp.components._python_op import InputPath, OutputPath
from kfp.dsl.io_types import Artifact, Input, Output, create_runtime_artifact, is_artifact_annotation, is_input_artifact, is_output_artifact


class Executor():
  """Executor executes v2-based Python function components."""

  def __init__(self, executor_input: Dict, function_to_execute: Callable):
    self._func = function_to_execute
    self._input = executor_input
    self._input_artifacts: Dict[str, Artifact] = {}
    self._output_artifacts: Dict[str, Artifact] = {}

    for name, artifacts in self._input.get('inputs', {}).get('artifacts',
                                                             {}).items():
      artifacts_list = artifacts.get('artifacts')
      if artifacts_list:
        self._input_artifacts[name] = self._make_input_artifact(
            artifacts_list[0])

    for name, artifacts in self._input.get('outputs', {}).get('artifacts',
                                                              {}).items():
      artifacts_list = artifacts.get('artifacts')
      if artifacts_list:
        self._output_artifacts[name] = self._make_output_artifact(
            artifacts_list[0])

    self._return_annotation = inspect.signature(self._func).return_annotation
    self._executor_output = {}

  @classmethod
  def _make_input_artifact(cls, runtime_artifact: Dict):
    return create_runtime_artifact(runtime_artifact)

  @classmethod
  def _make_output_artifact(cls, runtime_artifact: Dict):
    import os
    artifact = create_runtime_artifact(runtime_artifact)
    os.makedirs(os.path.dirname(artifact.path), exist_ok=True)
    return  artifact

  def _get_input_artifact(self, name: str):
    return self._input_artifacts.get(name)

  def _get_output_artifact(self, name: str):
    return self._output_artifacts.get(name)

  def _get_input_parameter_value(self, parameter_name: str):
    parameter = self._input.get('inputs', {}).get('parameters',
                                                  {}).get(parameter_name, None)
    if parameter is None:
      return None

    if parameter.get('stringValue'):
      return parameter['stringValue']
    elif parameter.get('intValue'):
      return int(parameter['intValue'])
    elif parameter.get('doubleValue'):
      return float(parameter['doubleValue'])

  def _get_output_parameter_path(self, parameter_name: str):
    parameter_name = self._maybe_strip_path_suffix(parameter_name)
    parameter = self._input.get('outputs',
                                {}).get('parameters',
                                        {}).get(parameter_name, None)
    if parameter is None:
      return None

    import os
    path = parameter.get('outputFile', None)
    if path:
      os.makedirs(os.path.basename(path), exist_ok=True)
    return path

  def _get_output_artifact_path(self, artifact_name: str):
    artifact_name = self._maybe_strip_path_suffix(artifact_name)
    output_artifact = self._output_artifacts.get(artifact_name)
    if not output_artifact:
      raise ValueError(
          'Failed to get output artifact path for artifact name {}'.format(
              artifact_name))
    return output_artifact.path

  def _get_input_artifact_path(self, artifact_name: str):
    artifact_name = self._maybe_strip_path_suffix(artifact_name)
    input_artifact = self._input_artifacts.get(artifact_name)
    if not input_artifact:
      raise ValueError(
          'Failed to get input artifact path for artifact name {}'.format(
              artifact_name))
    return input_artifact.path

  def _write_output_parameter_value(self, name: str, value: Union[str, int,
                                                                  float]):
    if type(value) == str:
      output = {"stringValue": value}
    elif type(value) == int:
      output = {"intValue": value}
    elif type(value) == float:
      output = {"doubleValue": value}
    else:
      raise RuntimeError(
          'Expected value of type str, int or float, got {} instead for value {}'
          .format(type(value), value))

    if not self._executor_output.get('parameters'):
      self._executor_output['parameters'] = {}

    self._executor_output['parameters'][name] = output

  def _write_output_artifact_payload(self, name: str, value: Any):
    path = self._get_output_artifact_path(name)
    with open(path, 'w') as f:
      f.write(str(value))

  @classmethod
  def _is_parameter(cls, annotation: Any) -> bool:
    return annotation in [str, int, float]

  @classmethod
  def _is_artifact(cls, annotation: Any) -> bool:
    if type(annotation) == type:
      return issubclass(annotation, Artifact)
    return False

  @classmethod
  def _is_named_tuple(cls, annotation: Any) -> bool:
    if type(annotation) == type:
      return issubclass(annotation, tuple) and hasattr(
          annotation, '_fields') and hasattr(annotation, '__annotations__')
    return False

  def _handle_single_return_value(self, output_name: str, annotation_type: Any,
                                  return_value: Any):
    if self._is_parameter(annotation_type):
      if type(return_value) != annotation_type:
        raise ValueError(
            'Function `{}` returned value of type {}; want type {}'.format(
                self._func.__name__, type(return_value), annotation_type))
      self._write_output_parameter_value(output_name, return_value)
    elif self._is_artifact(annotation_type):
      self._write_output_artifact_payload(output_name, return_value)
    else:
      raise RuntimeError(
          'Unknown return type: {}. Must be one of `str`, `int`, `float`, or a'
          ' subclass of `Artifact`'.format(annotation_type))

  def _write_executor_output(self, func_output: Optional[Any] = None):
    if self._output_artifacts:
      self._executor_output['artifacts'] = {}

    for name, artifact in self._output_artifacts.items():
      runtime_artifact = {
          "name": artifact.name,
          "uri": artifact.uri,
          "metadata": artifact.metadata,
      }
      artifacts_list = {'artifacts': [runtime_artifact]}

      self._executor_output['artifacts'][name] = artifacts_list

    if func_output is not None:
      if self._is_parameter(self._return_annotation) or self._is_artifact(
          self._return_annotation):
        # Note: single output is named `Output` in component.yaml.
        self._handle_single_return_value('Output', self._return_annotation,
                                         func_output)
      elif self._is_named_tuple(self._return_annotation):
        if len(self._return_annotation._fields) != len(func_output):
          raise RuntimeError(
              'Expected {} return values from function `{}`, got {}'.format(
                  len(self._return_annotation._fields), self._func.__name__,
                  len(func_output)))
        for i in range(len(self._return_annotation._fields)):
          field = self._return_annotation._fields[i]
          field_type = self._return_annotation.__annotations__[field]
          if type(func_output) == tuple:
            field_value = func_output[i]
          else:
            field_value = getattr(func_output, field)
          self._handle_single_return_value(field, field_type, field_value)
      else:
        raise RuntimeError(
            'Unknown return type: {}. Must be one of `str`, `int`, `float`, a'
            ' subclass of `Artifact`, or a NamedTuple collection of these types.'
            .format(self._return_annotation))

    import os
    os.makedirs(os.path.dirname(self._input['outputs']['outputFile']),
                exist_ok=True)
    with open(self._input['outputs']['outputFile'], 'w') as f:
      f.write(json.dumps(self._executor_output))

  def _maybe_strip_path_suffix(self, name) -> str:
    if name.endswith('_path'):
      name = name[0:-len('_path')]
    if name.endswith('_file'):
      name = name[0:-len('_file')]
    return name

  def execute(self):
    annotations = inspect.getfullargspec(self._func).annotations

    # Function arguments.
    func_kwargs = {}

    for k, v in annotations.items():
      if k == 'return':
        continue

      if v in [str, float, int]:
        func_kwargs[k] = self._get_input_parameter_value(k)

      if is_artifact_annotation(v):
        if is_input_artifact(v):
          func_kwargs[k] = self._get_input_artifact(k)
        if is_output_artifact(v):
          func_kwargs[k] = self._get_output_artifact(k)

      elif isinstance(v, OutputPath):
        if v.type in [str, float, int]:
          func_kwargs[k] = self._get_output_parameter_path(k)
        else:
          func_kwargs[k] = self._get_output_artifact_path(k)
      elif isinstance(v, InputPath):
        func_kwargs[k] = self._get_input_artifact_path(k)

    result = self._func(**func_kwargs)
    self._write_executor_output(result)
