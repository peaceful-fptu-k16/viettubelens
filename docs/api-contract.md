# API contract notes

The OpenAPI document served by `/openapi.json` is the source of truth. Important
semantic constraints:

- `sentiment_distribution` describes analysed relevant comments; it is not a
  demographic estimate of all viewers.
- `confidence_score` combines predictive separation and usable sample size.
- `insufficient_data` is a successful analysis that deliberately abstained.
- `unavailable` denotes a source limitation such as disabled comments.
- `source=demo` must always be disclosed in the client.
