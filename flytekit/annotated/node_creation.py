from __future__ import annotations

import collections
from typing import Type, Union

from flytekit.annotated.base_task import PythonTask
from flytekit.annotated.context_manager import BranchEvalMode, ExecutionState, FlyteContext
from flytekit.annotated.launch_plan import LaunchPlan
from flytekit.annotated.node import Node
from flytekit.annotated.promise import VoidPromise
from flytekit.annotated.workflow import Workflow
from flytekit.common.exceptions import user as _user_exceptions
from flytekit.loggers import logger

# This file exists instead of moving to node.py because it needs Task/Workflow/LaunchPlan and those depend on Node


def create_node(
    entity: Union[PythonTask, LaunchPlan, Workflow], *args, **kwargs
) -> Union[Node, VoidPromise, Type[collections.namedtuple]]:
    """
    This is the function you want to call if you need to specify dependencies between tasks that don't consume and/or
    don't produce outputs. For example, if you have t1() and t2(), both of which do not take in nor produce any
    outputs, how do you specify that t2 should run before t1?

        t2_node = create_node(t2)
        t1_node = create_node(t1)

        t2_node >> t1_node   # OR you can do,
        t1_node.depends_on(t2_node)

    This works for tasks that take inputs as well, say a ``t3(in1: int)``

        t3_node = create_node(t3, in1=some_int)  # basically calling t3(in1=some_int)

    You can still use this method to handle setting certain overrides

        t3_node = create_node(t3, in1=some_int).with_overrides(...)

    Outputs, if there are any, will be accessible. A `t4() -> (int, str)`

        t4_node = create_node(t4)

        in compilation node.o0 has the promise.
        t5(in1=t4_node.o0)

        in local workflow execution, what is the node?  Can it just be the named tuple?
        t5(in1=t4_node.o0)

    @workflow
    def wf():
        create_node(sub_wf)
        create_node(wf2)

    @dynamic
    def sub_wf():
        create_node(other_sub)
        create_node(task)

    If t1 produces only one output, note that in local execution, you still get a wrapper object that
    needs to be dereferenced by the output name.

        t1_node = create_node(t1)
        t2(t1_node.out_0)

    """
    if len(args) > 0:
        raise _user_exceptions.FlyteAssertion(
            f"Only keyword args are supported to pass inputs to workflows and tasks."
            f"Aborting execution as detected {len(args)} positional args {args}"
        )

    if not isinstance(entity, PythonTask) and not isinstance(entity, Workflow) and not isinstance(entity, LaunchPlan):
        raise AssertionError("Should be but it's not")

    # This function is only called from inside workflows and dynamic tasks.
    # That means there are two scenarios we need to take care of, compilation and local workflow execution.

    # When compiling, calling the entity will create a node.
    ctx = FlyteContext.current_context()
    if ctx.compilation_state is not None and ctx.compilation_state.mode == 1:

        outputs = entity(**kwargs)
        # This is always the output of create_and_link_node which returns create_task_output, which can be
        # VoidPromise, Promise, or our custom namedtuple of Promises.
        node = ctx.compilation_state.nodes[-1]

        # If a VoidPromise, just return the node.
        if isinstance(outputs, VoidPromise):
            return node

        # If a Promise or custom namedtuple of Promises, we need to attach each output as an attribute to the node.
        if entity.python_interface.outputs:
            if isinstance(outputs, tuple):
                for output_name in entity.python_interface.output_names:
                    attr = getattr(outputs, output_name)
                    if not attr:
                        raise Exception(f"Output {output_name} in outputs when calling {entity.name} is empty {attr}.")
                    setattr(node, output_name, attr)
            else:
                output_names = entity.python_interface.output_names
                if len(output_names) != 1:
                    raise Exception(f"Output of length 1 expected but {len(output_names)} found")

                setattr(node, output_names[0], outputs)  # This should be a singular Promise

        return node

    # Handling local execution
    elif ctx.execution_state is not None and ctx.execution_state.mode == ExecutionState.Mode.LOCAL_WORKFLOW_EXECUTION:
        if ctx.execution_state.branch_eval_mode == BranchEvalMode.BRANCH_SKIPPED:
            logger.warning(f"Manual node creation cannot be used in branch logic {entity.name}")
            raise Exception("Being more restrictive for now and disallowing manual node creation in branch logic")

        # This the output of __call__ under local execute conditions which means this is the output of _local_execute
        # which means this is the output of create_task_output with Promises containing values (or a VoidPromise)
        results = entity(**kwargs)

        # If it's a VoidPromise, let's just return it, it shouldn't get used anywhere and if it does, we want an error
        if isinstance(results, VoidPromise):
            return results

        output_names = entity.python_interface.output_names

        if not output_names:
            raise Exception(f"Non-VoidPromise received {results} but interface for {entity.name} doesn't have outputs")

        if len(output_names) == 1:
            # See explanation above for why we still tupletize a single element.
            return entity.python_interface.output_tuple(results)

        return entity.python_interface.output_tuple(*results)

    else:
        raise Exception(f"Cannot use explicit run to call Flyte entities {entity.name}")
