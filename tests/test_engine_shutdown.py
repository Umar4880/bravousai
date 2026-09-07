import importlib.util
import unittest
from unittest.mock import patch

HAS_PSYCOPG_POOL = importlib.util.find_spec("psycopg_pool") is not None

if HAS_PSYCOPG_POOL:
    from app.db import engine
else:
    engine = None


class FakeAsyncResource:
    def __init__(self) -> None:
        self.closed = False
        self.disposed = False

    async def close(self) -> None:
        self.closed = True

    async def dispose(self) -> None:
        self.disposed = True


@unittest.skipUnless(HAS_PSYCOPG_POOL, "psycopg_pool is not installed in this Python environment")
class EngineShutdownTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_app_engine = engine._app_engine
        self.original_checkpoint_engine = engine._checkpoint_engine
        self.original_checkpoint_pool = engine._checkpoint_pool
        self.original_session_factory = engine._session_factory

    def tearDown(self) -> None:
        engine._app_engine = self.original_app_engine
        engine._checkpoint_engine = self.original_checkpoint_engine
        engine._checkpoint_pool = self.original_checkpoint_pool
        engine._session_factory = self.original_session_factory

    async def test_dispose_checkpoint_engine_does_not_construct_engine(self) -> None:
        engine._checkpoint_engine = None

        with patch.object(engine, "_build_engine") as build_engine:
            await engine.dispose_checkpoint_engine_if_initialized()

        build_engine.assert_not_called()

    async def test_dispose_checkpoint_engine_closes_existing_engine(self) -> None:
        checkpoint_engine = FakeAsyncResource()
        engine._checkpoint_engine = checkpoint_engine

        await engine.dispose_checkpoint_engine_if_initialized()

        self.assertTrue(checkpoint_engine.disposed)
        self.assertIsNone(engine._checkpoint_engine)

    async def test_close_checkpoint_pool_does_not_construct_pool(self) -> None:
        engine._checkpoint_pool = None

        with patch.object(engine, "AsyncConnectionPool") as pool_class:
            await engine.close_checkpoint_pool_if_initialized()

        pool_class.assert_not_called()

    async def test_close_checkpoint_pool_closes_existing_pool(self) -> None:
        checkpoint_pool = FakeAsyncResource()
        engine._checkpoint_pool = checkpoint_pool

        await engine.close_checkpoint_pool_if_initialized()

        self.assertTrue(checkpoint_pool.closed)
        self.assertIsNone(engine._checkpoint_pool)

    async def test_dispose_app_engine_does_not_construct_engine(self) -> None:
        engine._app_engine = None
        engine._session_factory = object()

        with patch.object(engine, "_build_engine") as build_engine:
            await engine.dispose_app_engine_if_initialized()

        build_engine.assert_not_called()
        self.assertIsNotNone(engine._session_factory)

    async def test_dispose_app_engine_closes_existing_engine_and_factory(self) -> None:
        app_engine = FakeAsyncResource()
        engine._app_engine = app_engine
        engine._session_factory = object()

        await engine.dispose_app_engine_if_initialized()

        self.assertTrue(app_engine.disposed)
        self.assertIsNone(engine._app_engine)
        self.assertIsNone(engine._session_factory)


if __name__ == "__main__":
    unittest.main()
