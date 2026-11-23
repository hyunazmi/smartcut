class SnipyError(Exception):
    pass


class ToolNotFoundError(SnipyError):
    pass


class ProbeError(SnipyError):
    pass


class FFmpegError(SnipyError):
    pass


class CancelledError(SnipyError):
    pass
