"""Tests for the dependency injection container."""

import pytest

from audiobook_ripper.core.container import Container


class TestContainer:
    """Tests for the Container class."""

    def test_register_and_resolve(self):
        """Test registering and resolving a service."""
        container = Container()

        class IService:
            pass

        class ServiceImpl(IService):
            pass

        impl = ServiceImpl()
        container.register(IService, impl)

        resolved = container.resolve(IService)
        assert resolved is impl

    def test_resolve_unregistered_raises(self):
        """Test that resolving unregistered service raises KeyError."""
        container = Container()

        class IService:
            pass

        with pytest.raises(KeyError) as exc_info:
            container.resolve(IService)

        assert "IService" in str(exc_info.value)

    def test_register_factory(self):
        """Test registering a factory function."""
        container = Container()

        class IService:
            pass

        class ServiceImpl(IService):
            def __init__(self):
                self.created = True

        container.register_factory(IService, ServiceImpl)

        resolved = container.resolve(IService)
        assert isinstance(resolved, ServiceImpl)
        assert resolved.created

    def test_factory_creates_singleton(self):
        """Test that factory creates singleton on first resolve."""
        container = Container()

        class IService:
            pass

        call_count = 0

        class ServiceImpl(IService):
            def __init__(self):
                nonlocal call_count
                call_count += 1

        container.register_factory(IService, ServiceImpl)

        first = container.resolve(IService)
        second = container.resolve(IService)

        assert first is second
        assert call_count == 1

    def test_is_registered_true(self):
        """Test is_registered returns True for registered service."""
        container = Container()

        class IService:
            pass

        container.register(IService, object())
        assert container.is_registered(IService) is True

    def test_is_registered_false(self):
        """Test is_registered returns False for unregistered service."""
        container = Container()

        class IService:
            pass

        assert container.is_registered(IService) is False

    def test_is_registered_factory(self):
        """Test is_registered returns True for factory registration."""
        container = Container()

        class IService:
            pass

        container.register_factory(IService, lambda: object())
        assert container.is_registered(IService) is True

    def test_clear(self):
        """Test clearing all registrations."""
        container = Container()

        class IService:
            pass

        container.register(IService, object())
        assert container.is_registered(IService)

        container.clear()
        assert not container.is_registered(IService)

    def test_overwrite_registration(self):
        """Test that re-registering overwrites previous registration."""
        container = Container()

        class IService:
            pass

        first = object()
        second = object()

        container.register(IService, first)
        container.register(IService, second)

        assert container.resolve(IService) is second
