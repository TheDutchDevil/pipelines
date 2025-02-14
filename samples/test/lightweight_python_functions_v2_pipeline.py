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
"""Sample pipeline for passing data in KFP v2."""
from kfp import dsl
from kfp import components
from kfp.components import InputPath, OutputPath
from kfp.v2.dsl import Input, Output, Dataset, Model, component
import kfp.v2.compiler as compiler


@component
def preprocess(
    # An input parameter of type string.
    message: str,
    # Use Output[T] to get a metadata-rich handle to the output artifact
    # of type `Dataset`.
    output_dataset_one: Output[Dataset],
    # A locally accessible filepath for another output artifact of type
    # `Dataset`.
    output_dataset_two_path: OutputPath('Dataset'),
    # A locally accessible filepath for an output parameter of type string.
    output_parameter_path: OutputPath(str)
):
    '''Dummy preprocessing step'''

    # Use Dataset.path to access a local file path for writing.
    # One can also use Dataset.uri to access the actual URI file path.
    with open(output_dataset_one.path, 'w') as f:
        f.write(message)

    # OutputPath is used to just pass the local file path of the output artifact
    # to the function.
    with open(output_dataset_two_path, 'w') as f:
        f.write(message)

    with open(output_parameter_path, 'w') as f:
        f.write(message)


@component
def train(
    # Use InputPath to get a locally accessible path for the input artifact
    # of type `Dataset`.
    dataset_one_path: InputPath('Dataset'),
    # Use Input[T] to get a metadata-rich handle to the input artifact
    # of type `Dataset`.
    dataset_two: Input[Dataset],
    # An input parameter of type string.
    message: str,
    # Use Output[T] to get a metadata-rich handle to the output artifact
    # of type `Dataset`.
    model: Output[Model],
    # An input parameter of type int with a default value.
    num_steps: int = 100
):
    '''Dummy Training step'''
    with open(dataset_one_path, 'r') as input_file:
        dataset_one_contents = input_file.read()

    with open(dataset_two.path, 'r') as input_file:
        dataset_two_contents = input_file.read()

    line = "dataset_one_contents: {} || dataset_two_contents: {} || message: {}\n".format(
        dataset_one_contents, dataset_two_contents, message
    )

    with open(model.path, 'w') as output_file:
        for i in range(num_steps):
            output_file.write("Step {}\n{}\n=====\n".format(i, line))

    # Use `model` to get a Model artifact, which has a .metadata dictionary
    # to store arbitrary metadata for the output artifact.
    model.metadata['accuracy'] = 0.9



@dsl.pipeline(pipeline_root='dummy_root', name='my-test-pipeline-beta')
def pipeline(message: str = 'message'):
    preprocess_task = preprocess(message=message)
    train_task = train(
        dataset_one=preprocess_task.outputs['output_dataset_one'],
        dataset_two=preprocess_task.outputs['output_dataset_two'],
        message=preprocess_task.outputs['output_parameter'],
        num_steps=5
    )


if __name__ == '__main__':
    compiler.Compiler().compile(
        pipeline_func=pipeline,
        pipeline_root='dummy_root',
        output_path=__file__ + '.json'
    )
