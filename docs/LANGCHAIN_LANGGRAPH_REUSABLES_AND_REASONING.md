# LangChain, LangGraph, and Reasoning Response Notes

Local inspection used:

- `langchain==1.2.15`
- `langchain-core==1.2.28`
- `langgraph==1.1.6`
- Active Python: `C:\Users\hp\AppData\Local\Programs\Python\Python311\python.exe`
- `langchain-openai` and `openai` were not installed in the active interpreter during this inspection, although the app imports `langchain_openai.ChatOpenAI`.

## Classes Developers Should Know First

These are the classes that prevent rewriting common LangChain/LangGraph plumbing from scratch.

## LangChain Core

### Messages and content blocks

- `BaseMessage`: base type for all chat messages.
- `HumanMessage`, `AIMessage`, `SystemMessage`, `ToolMessage`, `ChatMessage`, `FunctionMessage`: standard message roles.
- `AIMessageChunk`, `HumanMessageChunk`, `SystemMessageChunk`, `ToolMessageChunk`: streaming message chunks.
- `ReasoningContentBlock`: standard block shape for reasoning summaries or provider reasoning text.
- `TextContentBlock`, `PlainTextContentBlock`, `ImageContentBlock`, `AudioContentBlock`, `VideoContentBlock`, `FileContentBlock`: typed multimodal content blocks.
- `ToolCall`, `ToolCallChunk`, `InvalidToolCall`, `ServerToolCall`, `ServerToolResult`: tool-call data models.

Useful properties:

- `AIMessage.content`: the main response payload.
- `AIMessage.text`: text accessor for final text.
- `AIMessage.content_blocks`: normalized typed blocks, including reasoning if the provider adapter preserved it.
- `AIMessage.additional_kwargs`: raw-ish provider extras.
- `AIMessage.response_metadata`: provider and token metadata.
- `AIMessage.usage_metadata`: normalized token usage.

### Models

- `BaseLanguageModel`: common model interface.
- `BaseChatModel`: base interface behind `.invoke()`, `.ainvoke()`, `.stream()`, `.astream()`.
- `SimpleChatModel`: lighter base class for custom chat models.
- `BaseLLM`, `LLM`: text model interfaces.
- `FakeChatModel`, `FakeListChatModel`, `FakeMessagesListChatModel`, `GenericFakeChatModel`, `ParrotFakeChatModel`: test doubles.
- `FakeListLLM`, `FakeStreamingListLLM`: LLM test doubles.

Key point: `BaseChatModel.invoke()` does not drop reasoning by itself. It returns `ChatGeneration.message`. Reasoning is lost earlier if the provider adapter does not put it into `content`, `content_blocks`, or `additional_kwargs`.

### Prompts

- `ChatPromptTemplate`: main chat prompt builder.
- `PromptTemplate`: string prompt builder.
- `MessagesPlaceholder`: inject existing chat history.
- `SystemMessagePromptTemplate`, `HumanMessagePromptTemplate`, `AIMessagePromptTemplate`, `ChatMessagePromptTemplate`: role-specific prompt pieces.
- `FewShotPromptTemplate`, `FewShotChatMessagePromptTemplate`: examples in prompts.
- `StructuredPrompt`: prompt with structured output expectations.

### Runnables

- `Runnable`: base composable unit.
- `RunnableSequence`: pipeline, usually created with `prompt | llm | parser`.
- `RunnableParallel` / `RunnableMap`: run branches in parallel.
- `RunnableLambda`: wrap a function as a runnable.
- `RunnablePassthrough`: pass input through, often with `.assign()`.
- `RunnableAssign`, `RunnablePick`: shape or select data.
- `RunnableBranch`: route by condition.
- `RunnableWithFallbacks`: fallback behavior. Your app already uses `primary.with_fallbacks([backup])`.
- `RunnableRetry`: retry behavior.
- `RunnableWithMessageHistory`: attach chat history management.
- `RunnableConfig`: standard config for callbacks, tags, metadata, run IDs, etc.

### Tools

- `BaseTool`: base tool class.
- `Tool`: simple function-backed tool.
- `StructuredTool`: schema-backed tool.
- `BaseToolkit`: group tools together.
- `InjectedToolArg`, `InjectedToolCallId`: inject runtime values into tools.
- `ToolException`: tool failure type.

### Output parsers

- `StrOutputParser`: convert model output to string.
- `JsonOutputParser`, `SimpleJsonOutputParser`: JSON parsing.
- `PydanticOutputParser`: parse into Pydantic models.
- `PydanticToolsParser`, `JsonOutputToolsParser`, `JsonOutputKeyToolsParser`: tool-call output parsing.
- `PydanticOutputFunctionsParser`, `JsonOutputFunctionsParser`, `JsonKeyOutputFunctionsParser`: OpenAI function-call style parsing.
- `XMLOutputParser`, `ListOutputParser`, `MarkdownListOutputParser`, `NumberedListOutputParser`, `CommaSeparatedListOutputParser`: common structured text parsers.

### Documents, retrieval, embeddings, vector stores

- `Document`, `Blob`: document primitives.
- `BaseLoader`, `BaseBlobParser`, `BlobLoader`: loading/parsing primitives.
- `BaseRetriever`: retrieval interface.
- `VectorStore`, `VectorStoreRetriever`, `InMemoryVectorStore`: vector store abstractions.
- `Embeddings`, `FakeEmbeddings`, `DeterministicFakeEmbedding`: embedding interfaces/test doubles.
- `BaseDocumentTransformer`, `BaseDocumentCompressor`: document transformation/compression.
- `DocumentIndex`, `InMemoryDocumentIndex`, `RecordManager`, `InMemoryRecordManager`: indexing primitives.

### Callbacks, tracing, rate limiting, cache

- `BaseCallbackHandler`, `AsyncCallbackHandler`: custom callback hooks.
- `CallbackManager`, `AsyncCallbackManager`: callback dispatch.
- `CallbackManagerForLLMRun`, `AsyncCallbackManagerForLLMRun`: LLM run callbacks.
- `LangChainTracer`, `ConsoleCallbackHandler`, `StreamingStdOutCallbackHandler`, `UsageMetadataCallbackHandler`: tracing and output callbacks.
- `BaseRateLimiter`, `InMemoryRateLimiter`: rate limiting.
- `BaseCache`, `InMemoryCache`: LLM caching.

## LangChain Agent Classes

In `langchain==1.2.15`, most agent value is in `create_agent()` plus middleware classes:

- `AgentMiddleware`, `AgentState`, `ModelRequest`, `ModelResponse`, `ExtendedModelResponse`: agent middleware types.
- `HumanInTheLoopMiddleware`, `ActionRequest`, `HITLRequest`, `HITLResponse`, `ApproveDecision`, `EditDecision`, `RejectDecision`: human approval flows.
- `ModelFallbackMiddleware`, `ModelRetryMiddleware`, `ModelCallLimitMiddleware`: model reliability/limits.
- `ToolRetryMiddleware`, `ToolCallLimitMiddleware`, `LLMToolSelectorMiddleware`, `LLMToolEmulator`: tool behavior.
- `PIIMiddleware`, `RedactionRule`, `PIIMatch`: PII handling.
- `SummarizationMiddleware`: conversation summarization.
- `TodoListMiddleware`, `Todo`, `PlanningState`: planning/todo state.
- `FilesystemFileSearchMiddleware`: file search.
- `ShellToolMiddleware`, `ShellSession`, `CommandExecutionResult`: shell tool behavior.
- `ProviderStrategy`, `ToolStrategy`, `AutoStrategy`: structured output strategies.

## LangGraph

### Graph construction

- `StateGraph`: primary class for building stateful graphs.
- `CompiledStateGraph`: compiled runnable graph returned by `.compile()`.
- `MessageGraph`: message-oriented graph.
- `MessagesState`: prebuilt message state schema.
- `END`: graph termination marker.
- `Command`: return type for control flow, updates, and routing.
- `Send`: fan-out to nodes dynamically.
- `Interrupt`: interrupt/pause graph execution.
- `Overwrite`: overwrite state channel values.

### Prebuilt agent/tool pieces

- `ToolNode`: execute tool calls from model messages.
- `ValidationNode`: validate tool calls.
- `InjectedState`, `InjectedStore`: inject graph state/store into tools.
- `ToolRuntime`, `ToolCallRequest`, `ToolCallWithContext`: tool runtime models.
- `HumanInterrupt`, `HumanInterruptConfig`, `HumanResponse`, `ActionRequest`: human-in-the-loop interrupt objects.
- `AgentState`, `AgentStateWithStructuredResponse`: prebuilt agent state shapes.

### Runtime, state, and streaming

- `Runtime`, `ExecutionInfo`, `ServerInfo`: runtime context.
- `StateSnapshot`, `StateUpdate`: inspect/update graph state.
- Stream part classes: `ValuesStreamPart`, `UpdatesStreamPart`, `MessagesStreamPart`, `TasksStreamPart`, `DebugStreamPart`, `CustomStreamPart`, `CheckpointStreamPart`.
- `RetryPolicy`, `CachePolicy`, `CacheKey`: graph retry/cache behavior.

### Channels

- `BaseChannel`: channel base.
- `LastValue`: keep last value.
- `BinaryOperatorAggregate`: aggregate updates with an operator.
- `Topic`: pub/sub-like accumulation.
- `EphemeralValue`: transient value.
- `AnyValue`, `UntrackedValue`, `NamedBarrierValue`: specialized channels.

### Lower-level execution

- `Pregel`: lower-level execution engine.
- `PregelNode`, `ChannelRead`, `ChannelWrite`, `NodeBuilder`: low-level graph internals.
- `RemoteGraph`: call a remote LangGraph graph.

Most app developers should use `StateGraph`, `Command`, `Send`, `ToolNode`, checkpointers, and stream modes before touching `Pregel` internals.

## Where Reasoning Is Lost

`BaseChatModel.invoke()` simply calls `generate_prompt(...).generations[0][0].message`.

`BaseChatModel.stream()` yields `AIMessageChunk` objects returned by `_stream()`.

So if reasoning is missing from `AIMessage`, the loss usually happens inside the provider integration, for example `ChatOpenAI`, when it converts the raw provider response into:

- `AIMessage(content=...)`
- `AIMessageChunk(content=...)`
- `ChatGeneration(message=...)`
- `ChatGenerationChunk(message=...)`

Your local `langchain_core` already knows about reasoning:

- `ReasoningContentBlock` exists.
- `AIMessage.content_blocks` extracts `additional_kwargs["reasoning_content"]` if it exists as a string.
- The OpenAI block translator can convert OpenAI Responses API `{"type": "reasoning", "summary": [...]}` blocks into standard reasoning blocks.

That means the fix is to make sure the provider adapter preserves the raw reasoning field.

## Best Fix for Official OpenAI Responses API

For official OpenAI reasoning summaries, prefer constructor-level support instead of overriding methods:

```python
reasoning = None
if setting.DO_REASONING_ENABLED:
    reasoning = {
        "effort": setting.DO_REASONING_EFFORT,
        "summary": "auto",
    }

llm = ChatOpenAI(
    base_url=setting.DO_BASE_URL,
    api_key=setting.DO_API_KEY,
    model=setting.DO_MODEL,
    temperature=setting.TEMPERATURE,
    streaming=True,
    reasoning=reasoning,
    use_responses_api=True,
    callbacks=[logger],
)
```

Then read:

```python
response = await llm.ainvoke(messages)
reasoning_blocks = [
    block
    for block in response.content_blocks
    if block["type"] == "reasoning"
]
```

Important: OpenAI exposes reasoning summaries, not raw hidden reasoning tokens.

## Fix for Third-Party OpenAI-Compatible Providers

LangChain's `ChatOpenAI` targets official OpenAI response shapes. Third-party fields like `reasoning_content`, `reasoning`, or `reasoning_details` may be ignored by the adapter. If your raw SDK response contains those fields, subclass the provider model and override the conversion point, not `invoke()` itself.

The target behavior is:

```python
AIMessage(
    content=final_text,
    additional_kwargs={
        "reasoning_content": raw_reasoning_text,
        "raw_response": raw_response_dict,
    },
    response_metadata=metadata,
)
```

Then this works automatically:

```python
for block in ai_message.content_blocks:
    if block["type"] == "reasoning":
        print(block["reasoning"])
```

### Subclass Pattern

Exact method names depend on the installed `langchain-openai` version, but the shape is:

```python
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_openai import ChatOpenAI


class ReasoningChatOpenAI(ChatOpenAI):
    def _convert_dict_to_message(self, raw: dict[str, Any]) -> AIMessage:
        message = super()._convert_dict_to_message(raw)
        reasoning = (
            raw.get("reasoning_content")
            or raw.get("reasoning")
            or raw.get("reasoning_details")
        )
        if reasoning:
            message.additional_kwargs["reasoning_content"] = (
                reasoning if isinstance(reasoning, str) else str(reasoning)
            )
            message.additional_kwargs["raw_response"] = raw
        return message

    def _convert_delta_to_message_chunk(
        self,
        raw: dict[str, Any],
        default_class: type[AIMessageChunk] = AIMessageChunk,
    ) -> AIMessageChunk:
        chunk = super()._convert_delta_to_message_chunk(raw, default_class)
        reasoning = (
            raw.get("reasoning_content")
            or raw.get("reasoning")
            or raw.get("reasoning_details")
        )
        if reasoning:
            chunk.additional_kwargs["reasoning_content"] = (
                reasoning if isinstance(reasoning, str) else str(reasoning)
            )
            chunk.additional_kwargs["raw_response_delta"] = raw
        return chunk
```

If the installed `ChatOpenAI` has module-level conversion functions rather than instance methods, copy the class and override `_generate()` / `_stream()` to call the raw client and construct `ChatResult` / `ChatGenerationChunk` yourself. Keep the output as `AIMessage` and `AIMessageChunk`, because LangGraph and LCEL already understand those types.

## Recommended App Change

In `app/core/llm_provider.py`, change from provider-specific `extra_body` reasoning to official `reasoning` when the endpoint supports OpenAI Responses API:

```python
reasoning = None
if setting.DO_REASONING_ENABLED:
    reasoning = {"effort": setting.DO_REASONING_EFFORT, "summary": "auto"}

return ChatOpenAI(
    base_url=setting.DO_BASE_URL,
    api_key=setting.DO_API_KEY,
    model=setting.DO_MODEL,
    temperature=setting.TEMPERATURE,
    streaming=True,
    reasoning=reasoning,
    use_responses_api=bool(reasoning),
    callbacks=[logger],
)
```

If DigitalOcean returns non-standard reasoning fields instead of OpenAI Responses API reasoning blocks, use `ReasoningChatOpenAI` and preserve `reasoning_content` in `additional_kwargs`.

## Minimal Helper

Use this helper anywhere you receive an `AIMessage`:

```python
from langchain_core.messages import AIMessage


def extract_reasoning(message: AIMessage) -> list[str]:
    values: list[str] = []
    for block in message.content_blocks:
        if block["type"] == "reasoning" and block.get("reasoning"):
            values.append(block["reasoning"])
    raw = message.additional_kwargs.get("reasoning_content")
    if isinstance(raw, str) and raw not in values:
        values.append(raw)
    return values
```

For streaming, aggregate chunks first or collect reasoning chunk text from each chunk's `additional_kwargs["reasoning_content"]`.

