from django.core.files.uploadhandler import MemoryFileUploadHandler, StopUpload


MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_MULTIPART_OVERHEAD = 64 * 1024
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + MAX_MULTIPART_OVERHEAD


class UploadSizeLimitHandler(MemoryFileUploadHandler):
    """Reject oversized uploads before later handlers spool file content."""

    def __init__(self, request=None):
        super().__init__(request)
        self._received = 0

    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):
        if content_length and content_length > MAX_REQUEST_BYTES:
            raise StopUpload(connection_reset=True)
        self._received = 0
        self.activated = bool(content_length and content_length <= MAX_REQUEST_BYTES)

    def receive_data_chunk(self, raw_data, start):
        self._received += len(raw_data)
        if self._received > MAX_REQUEST_BYTES:
            raise StopUpload(connection_reset=True)
        if self.activated:
            return super().receive_data_chunk(raw_data, start)
        return raw_data

    def file_complete(self, file_size):
        if self.activated:
            return super().file_complete(file_size)
        return None
