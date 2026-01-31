"""Dependency injection container."""

from typing import Any, TypeVar

T = TypeVar("T")


class Container:
    """Simple dependency injection container."""

    def __init__(self) -> None:
        self._services: dict[type, Any] = {}
        self._factories: dict[type, Any] = {}

    def register(self, interface: type[T], implementation: T) -> None:
        """Register a singleton instance for an interface."""
        self._services[interface] = implementation

    def register_factory(self, interface: type[T], factory: Any) -> None:
        """Register a factory function for an interface."""
        self._factories[interface] = factory

    def resolve(self, interface: type[T]) -> T:
        """Resolve an instance for the given interface."""
        if interface in self._services:
            return self._services[interface]
        if interface in self._factories:
            instance = self._factories[interface]()
            self._services[interface] = instance
            return instance
        raise KeyError(f"No registration found for {interface.__name__}")

    def is_registered(self, interface: type) -> bool:
        """Check if an interface is registered."""
        return interface in self._services or interface in self._factories

    def clear(self) -> None:
        """Clear all registrations."""
        self._services.clear()
        self._factories.clear()
