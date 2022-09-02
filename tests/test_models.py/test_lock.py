import asyncio
import dataclasses

# "pypedal.server.models.ProcessModel" Class Representation
@dataclasses.dataclass
class HasLockAlreadyModel:
    lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)


def test_attr():
    model = HasLockAlreadyModel()
    another_model = HasLockAlreadyModel()
    assert model.lock
    assert another_model.lock is not model.lock


async def test_lock():
    model = HasLockAlreadyModel()
    another_model = HasLockAlreadyModel()

    async with model.lock:
        assert model.lock.locked()
        assert not another_model.lock.locked()
        async with another_model.lock:
            assert another_model.lock.locked()
            assert model.lock.locked()
        assert model.lock.locked()
        assert not another_model.lock.locked()
