import pytest
from synapse.work import Approval, ApprovalDecision, Budget, CostRecord, Run, Task, WorkEngine, WorkStatus

@pytest.mark.asyncio
async def test_atomic_checkout_only_one_owner():
    e=WorkEngine(); task=await e.create_task(Task(title="exclusive"))
    first=await e.checkout(task.id,"worker-a"); second=await e.checkout(task.id,"worker-b")
    assert first is not None and second is None
    assert await e.heartbeat(first) is True
    assert await e.release(first,WorkStatus.COMPLETED) is True
    await e.close()

@pytest.mark.asyncio
async def test_run_approval_budget_and_cost_are_durable():
    e=WorkEngine(); task=await e.create_task(Task(title="job")); run=await e.create_run(Run(task_id=task.id))
    approval=await e.create_approval(Approval(task_id=task.id,action="deploy"))
    assert await e.decide_approval(approval.id,ApprovalDecision.ALLOW_ONCE,"admin") is True
    assert await e.decide_approval(approval.id,ApprovalDecision.DENY,"admin") is False
    await e.create_budget(Budget(scope_id=task.id,limit_usd=10))
    assert await e.record_cost(CostRecord(run_id=run.id,provider_id="p",model_id="m",cost_usd=1.25))
    await e.close()

@pytest.mark.asyncio
async def test_expired_lease_can_be_reclaimed():
    e=WorkEngine(); task=await e.create_task(Task(title="retry")); lease=await e.checkout(task.id,"a",lease_seconds=0); assert lease
    reclaimed=await e.checkout(task.id,"b",lease_seconds=30); assert reclaimed is not None
    await e.close()
