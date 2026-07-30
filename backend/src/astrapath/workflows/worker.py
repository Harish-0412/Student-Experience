import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from astrapath.config import get_settings
from astrapath.workflows.temporal_poc import (
    PhaseOneGoalWorkflow,
    evaluate_profile_activity,
    prepare_goal_activity,
)


async def run_worker() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[PhaseOneGoalWorkflow],
        activities=[evaluate_profile_activity, prepare_goal_activity],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
