"""Safe provider diagnostics: controlled reasons, never SDK strings or secrets."""
class ProviderError(RuntimeError):
    def __init__(self, category, message):
        super().__init__(message)
        self.category, self.safe_message = category, message


def diagnostic(exc):
    if isinstance(exc, ProviderError):
        return exc.category, exc.safe_message
    # Inspect locally for classification only; never forward the original message.
    name = type(exc).__name__
    text = str(exc).lower()
    if 'timeout' in name.lower() or name == 'TimeoutExpired':
        return 'TIMEOUT', 'Provider request exceeded its bounded timeout.'
    if any(word in text for word in ['unauthorized', 'authentication', 'forbidden', 'credentials']):
        return 'AUTHENTICATION', 'Provider authentication or access authorization failed.'
    if any(word in text for word in ['dataset not', 'dataset id', 'dataset_id']):
        return 'DATASET_LOOKUP', 'Configured dataset could not be resolved by the provider.'
    if 'variable' in text:
        return 'VARIABLE_LOOKUP', 'Requested variable could not be resolved in the selected dataset.'
    if any(word in text for word in ['temporal', 'time range', 'time bounds', 'date range']):
        return 'TEMPORAL_COVERAGE', 'Requested times are outside available provider coverage.'
    if any(word in text for word in ['latitude', 'longitude', 'spatial', 'bounding']):
        return 'SPATIAL_COVERAGE', 'Requested location is outside available provider coverage.'
    if 'depth' in text:
        return 'DEPTH_SELECTION', 'Requested vertical level is missing or incompatible.'
    if name == 'KeyError':
        return 'MISSING_FIELD', 'A required provider response field is missing.'
    return 'PROVIDER_RUNTIME', 'Provider library/runtime failed; no usable evidence returned.'
