class ServiceError(Exception):
    pass


class ProviderNotConfigured(ServiceError):
    pass


class LLMError(ServiceError):
    pass


class ImageGenerationError(ServiceError):
    pass


class RendererError(ServiceError):
    pass
