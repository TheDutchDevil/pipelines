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

from kfp import components
from kfp import dsl
import kfp.v2.compiler as compiler


@components.create_component_from_func
def print_op(msg: str):
  print(msg)


@dsl.pipeline(
    name='pipeline-with-loops-and-conditions',
    pipeline_root='dummy_root',
)
def my_pipeline(
    text_parameter:str
    ='[{"p_a": [{"q_a":1}, {"q_a":2}], "p_b": "hello"}, {"p_a": [{"q_a":11},{"q_a":22}], "p_b": "halo"}]'):
  with dsl.ParallelFor(text_parameter) as item:
    with dsl.ParallelFor(item.p_a) as item_p_a:
      print_op(item_p_a.q_a)


if __name__ == '__main__':
  compiler.Compiler().compile(
      pipeline_func=my_pipeline, package_path=__file__.replace('.py', '.json'))
