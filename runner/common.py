from typing import Any, Awaitable, Callable, Protocol, Set, TypeVar

T = TypeVar("T", covariant=True)

RunnerEventHandler = Callable[..., None] | Callable[..., Awaitable[None]]


class GetServiceContext(Protocol):
    def __enter__(self) -> "GetServiceContext":
        ...


class FactoryCallableTwoArguments(Protocol):
    def __call__(
        self,
        context: GetServiceContext,
        parent_type: type,
    ) -> Any:
        ...


class FactoryCallableNoArguments(Protocol):
    def __call__(
        self,
    ) -> Any:
        ...


class FactoryCallableSingleArgument(Protocol):
    def __call__(
        self,
        context: GetServiceContext,
    ) -> Any:
        ...


FactoryCallableType = (
    FactoryCallableNoArguments
    | FactoryCallableSingleArgument
    | FactoryCallableTwoArguments
)


class Provider(Protocol):
    map: dict[str | type, FactoryCallableType]

    def __contains__(self, item: str | type) -> bool:
        ...

    def __getitem__(self, item: str | type) -> Any:
        ...

    def __setitem__(self, key: type, value: Any):
        ...

    def set(self, new_type: type, value: Any):
        ...

    def get(
        self,
        desired_type: type[T] | str,
        context: GetServiceContext | None = None,
        *,
        default: Any = None,
    ) -> T:
        ...

    def resolve_params(
        self,
        method: Callable[[], Any],
        exclude_names: Set[str] | None = None,
    ) -> dict[str, Any]:
        ...

    def wrap(
        self,
        method: Callable[[], Any],
        exclude_names: Set[str] | None = None,
    ) -> Callable[..., Any]:
        ...


class Container(Protocol):
    def __init__(self, strict: bool = False):
        ...

    def add_instance(
        self,
        instance: Any,
        declared_class: type | None = None,
    ) -> "Container":
        ...

    def add_singleton(
        self,
        base_type: type,
        concrete_type: type | None = None,
    ) -> "Container":
        ...

    def add_scoped(
        self,
        base_type: type,
        concrete_type: type | None = None,
    ) -> "Container":
        ...

    def add_transient(
        self,
        base_type: type,
        concrete_type: type | None = None,
    ) -> "Container":
        ...

    def add_exact_singleton(
        self,
        concrete_type: type,
    ) -> "Container":
        ...

    def add_exact_scoped(
        self,
        concrete_type: type,
    ) -> "Container":
        ...

    def add_exact_transient(
        self,
        concrete_type: type,
    ) -> "Container":
        ...

    def add_singleton_by_factory(
        self,
        factory: FactoryCallableType,
        return_type: type | None = None,
    ) -> "Container":
        ...

    def add_transient_by_factory(
        self,
        factory: FactoryCallableType,
        return_type: type | None = None,
    ) -> "Container":
        ...

    def add_scoped_by_factory(
        self,
        factory: FactoryCallableType,
        return_type: type | None = None,
    ) -> "Container":
        ...

    def build_provider(self) -> Provider:
        ...
