class AetherError(Exception):
    exit_code = 1


class ConfigError(AetherError):
    pass


class ProviderError(AetherError):
    def __init__(self, message, provider="", status_code=None, retryable=False, payload=None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable
        self.payload = payload or {}


class AuthenticationError(ProviderError):
    pass


class RateLimitError(ProviderError):
    pass


class ToolError(AetherError):
    pass


class PermissionDenied(ToolError):
    pass


class ApprovalRequired(PermissionDenied):
    pass


class ContextOverflow(AetherError):
    pass


class Cancelled(AetherError):
    pass


class SkillError(AetherError):
    pass


class SchedulerError(AetherError):
    pass


class OrchestratorError(AetherError):
    pass
