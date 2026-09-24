from django.core.files.uploadhandler import FileUploadHandler, StopUpload


MAX_UPLOAD_BYTES = 2 * 1024 * 1024


class UploadSizeLimitHandler(FileUploadHandler):
    """Reject oversized uploads before later handlers spool file content."""

    def __init__(self, request=None):
        super().__init__(request)
        self._received = 0

    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):
        if content_length and content_length > MAX_UPLOAD_BYTES:
            raise StopUpload(connection_reset=True)

    def receive_data_chunk(self, raw_data, start):
        self._received += len(raw_data)
        if self._received > MAX_UPLOAD_BYTES:
            raise StopUpload(connection_reset=True)
        return None

    def file_complete(self, file_size):
        return None
