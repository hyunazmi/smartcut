class SmartcutError(Exception):
    pass


class ToolNotFoundError(SmartcutError):
    pass


class ProbeError(SmartcutError):
    pass


class FFmpegError(SmartcutError):
    pass


class CancelledError(SmartcutError):
    pass
