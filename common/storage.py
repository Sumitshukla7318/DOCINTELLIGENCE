def generate_file_url(file_field, request=None) -> str | None:
    if not file_field:
        return None
    if request:
        return request.build_absolute_uri(file_field.url)
    return file_field.url