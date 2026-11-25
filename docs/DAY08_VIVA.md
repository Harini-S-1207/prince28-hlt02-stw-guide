# Day 08 – LLM Gateway Viva Questions

## 1. What is an LLM Gateway?

An LLM Gateway is a centralized component that manages communication between an application and different language model providers.

## 2. Why did we implement an LLM Gateway?

To manage multiple providers, retries, fallback, streaming, error handling and usage tracking from one place.

## 3. Which providers are integrated?

- Gemini – Primary provider.

- Groq – Fallback provider.

Both are accessed through an OpenAI-compatible interface.

## 4. What is an OpenAI-compatible API?

It is an API that follows the OpenAI request and response format, allowing compatible providers to use a common integration pattern.

## 5. What is retry handling?

Retry handling means attempting a failed request again when the error is temporary and retryable, using a delay between attempts.

## 6. What is exponential backoff?

It increases the waiting time between retry attempts to avoid repeatedly sending requests to an overloaded provider.

## 7. What is a circuit breaker?

A circuit breaker temporarily stops requests to a failing provider to prevent repeated failures.

## 8. What is fallback?

Fallback means using another configured provider when the primary provider cannot complete a request.

## 9. What is the purpose of FakeLLM?

FakeLLM simulates an LLM provider during testing, allowing tests to run without depending on real API calls.

## 10. How does streaming work?

The gateway sends response pieces as they are generated instead of waiting for the complete answer.

## 11. Why should we not switch providers in the middle of a streamed answer?

Switching providers after sending part of an answer can create an inconsistent or duplicated response. Therefore, fallback is allowed only before the first response piece.

## 12. What is LLM usage tracking?

It records information about model calls, such as provider, model, token counts, latency, status and estimated cost.

## 13. Why do we store usage information in PostgreSQL?

PostgreSQL provides persistent storage, allowing us to analyze and retrieve usage information later.

## 14. What is token estimation?

Token estimation calculates an approximate number of input and output tokens used by a model request.

## 15. What does UsageRepository.by\_day() do?

It retrieves aggregated LLM usage information grouped by day for the requested number of days.

## 16. How did we test the LLM Gateway?

We used pytest and FakeLLM to test retries, fallback, circuit breaker behaviour, streaming and error handling without relying entirely on live providers.

## 17. What is branch coverage?

Branch coverage measures whether both possible outcomes of decision points, such as `if` and `else`, have been tested.

## 18. What was the final Day 08 test coverage?

The final verified full-project report showed:

- Statements: 1,196

- Missed statements: 0

- Branches: 258

- Partial branches: 0

- Statement coverage: 100%

- Branch coverage: 100%

## 19. Which API endpoints were added?

- `POST /v1/chat` – Streams AI chat responses.

- `GET /v1/usage` – Returns daily LLM usage statistics.

## 20. What happens if all configured LLM providers fail?

The gateway reports an LLM unavailable error. The chat endpoint returns a safe error event instead of exposing internal provider details.
