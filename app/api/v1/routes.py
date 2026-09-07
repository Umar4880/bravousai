import uuid
from typing import Any
import asyncio

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
import json

from app.domain.schemas.requests_schemas.chat_request import ChatRequest
from app.db.unit_of_work import UnitOfWork

import logging
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/chat", tags=["chat"])


def _chat_service_from_request(request: Request):
	service = getattr(request.app.state, "chat_service", None)
	return service 


@router.get("/conversations")
async def list_conversations(
	user_id: uuid.UUID = Query(...),
	project_id: str | None = Query(None),
	limit: int = Query(50, ge=1, le=100),
	offset: int = Query(0, ge=0),
) -> dict:
	parsed_project_id: uuid.UUID | None = None
	if project_id:
		try:
			parsed_project_id = uuid.UUID(project_id)
		except ValueError:
			# Non-UUID project ID (e.g. mock or guest projects like "enterprise-rag-architecture")
			return {"conversations": []}

	try:
		async with UnitOfWork() as uow:
			if parsed_project_id is not None:
				conversations = await uow.conversations.list_by_project(
					project_id=parsed_project_id,
					user_id=str(user_id),
					limit=limit,
					offset=offset,
				)
			else:
				conversations = await uow.conversations.list_by_user(
					user_id=user_id,
					limit=limit,
					offset=offset,
				)
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc

	return {
		"conversations": [
			{
				"id": str(conversation.id),
				"title": conversation.title,
				"created_at": conversation.created_at.isoformat(),
			}
			for conversation in conversations
		]
	}


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
	conversation_id: uuid.UUID,
	user_id: uuid.UUID = Query(...),
	limit: int = Query(50, ge=1, le=100),
) -> dict:
	try:
		async with UnitOfWork() as uow:
			conversation = await uow.conversations.get_by_id(
				conversation_id=conversation_id,
				user_id=user_id,
			)
			if conversation is None:
				raise HTTPException(status_code=404, detail="Conversation not found.")

			messages = await uow.messages.get_history(
				conversation_id=conversation_id,
				user_id=user_id,
				limit=limit,
			)
			traces = {}
			for message in messages:
				if message.role != "user":
					continue

				workflow_record = await uow.workflow_records.get_for_message(
					conversation_id=conversation_id,
					user_id=str(user_id),
					message_id=message.id,
				)
				research_plan = await uow.research_traces.get_research_plan_for_message(
					conversation_id=conversation_id,
					user_id=str(user_id),
					message_id=message.id,
				)
				fetched_urls = await uow.research_traces.list_fetched_urls(
					conversation_id=conversation_id,
					user_id=str(user_id),
					research_plan_id=research_plan.id if research_plan else None,
					message_id=message.id,
				)
				artifacts = await uow.artifacts.list_for_message(
					conversation_id=conversation_id,
					user_id=str(user_id),
					message_id=message.id,
					limit=5,
				)
				trace = _build_trace_payload(
					workflow_record=workflow_record,
					research_plan=research_plan,
					fetched_urls=fetched_urls,
					artifacts=artifacts,
				)
				if trace["steps"] or trace["answer"]:
					traces[str(message.id)] = trace
	except HTTPException:
		raise
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc

	return {
		"conversation": {
			"id": str(conversation.id),
			"title": conversation.title,
			"created_at": conversation.created_at.isoformat(),
			"project_id": str(conversation.project_id),
		},
		"messages": [
			{
				"id": str(message.id),
				"role": message.role,
				"content": message.content,
				"created_at": message.created_at.isoformat(),
			}
			for message in messages
		],
		"traces": traces,
	}


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
	conversation_id: uuid.UUID,
	user_id: uuid.UUID = Query(...),
	payload: dict[str, str] = Body(...),
) -> dict:
	title = " ".join((payload.get("title") or "").split())[:128]
	if not title:
		raise HTTPException(status_code=422, detail="Title is required.")

	try:
		async with UnitOfWork() as uow:
			updated = await uow.conversations.update_title(
				conversation_id=conversation_id,
				user_id=str(user_id),
				title=title,
			)
			if not updated:
				raise HTTPException(status_code=404, detail="Conversation not found.")
			await uow.commit()
	except HTTPException:
		raise
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc

	return {
		"id": str(conversation_id),
		"title": title,
	}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
	conversation_id: uuid.UUID,
	user_id: uuid.UUID = Query(...),
) -> dict:
	try:
		async with UnitOfWork() as uow:
			deleted = await uow.conversations.delete(
				conversation_id=conversation_id,
				user_id=str(user_id),
			)
			if not deleted:
				raise HTTPException(status_code=404, detail="Conversation not found.")
			await uow.commit()
	except HTTPException:
		raise
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc

	return {"deleted": True, "id": str(conversation_id)}


def _build_trace_payload(
	*,
	workflow_record: Any,
	research_plan: Any,
	fetched_urls: list[Any],
	artifacts: list[Any],
) -> dict[str, Any]:
	steps: list[dict[str, Any]] = []
	answer = ""
	active_artifact = None

	if workflow_record is not None:
		steps.append({
			"node": "supervisor",
			"label": "Planning workflow complete.",
			"status": "done",
			"isOpen": False,
			"content": "Workflow selected. I routed the request to the right specialist steps.",
			"sources": [],
		})

	if research_plan is not None:
		plan_json = research_plan.plan_json or {}
		query_count = len(plan_json.get("search_queries") or []) if isinstance(plan_json, dict) else 0
		steps.append({
			"node": "research_plan",
			"label": "Planning research complete.",
			"status": "done",
			"isOpen": False,
			"content": (
				f"Research plan ready. I checked {query_count or 'multiple'} targeted "
				"search paths and prioritized source-backed evidence."
			),
			"sources": [],
		})

	if fetched_urls:
		steps.append({
			"node": "research_search",
			"label": "Searching on internet complete.",
			"status": "done",
			"isOpen": False,
			"content": "\n".join(
				f"Searching for: {item.query}" for item in fetched_urls if item.query
			),
			"sources": [
				{
					"id": f"{item.url}-{index}",
					"title": item.title or item.url,
					"url": item.url,
					"favicon": None,
				}
				for index, item in enumerate(fetched_urls)
				if item.url
			],
		})

	if research_plan is not None and research_plan.synthesized_content:
		steps.append({
			"node": "research_synthesize",
			"label": "Synthesizing result complete.",
			"status": "done",
			"isOpen": False,
			"content": "Evidence reviewed and organized for the final response.",
			"sources": [],
		})

	for artifact in reversed(artifacts):
		if artifact.artifact_type not in {"report", "research_package", "html_artifact"}:
			continue

		if artifact.artifact_type == "report":
			answer = artifact.content

		node = "writer"
		label = "Crafting report complete."
		content = ""

		if artifact.artifact_type == "research_package":
			node = "research_artifact"
			label = "Research package complete."
			content = "Research package prepared for the final response."
		elif artifact.artifact_type == "html_artifact":
			node = "presentation"
			label = "Building interactive artifact complete."
			content = "Visual artifact prepared for the final response."
			if hasattr(artifact, "versions") and artifact.versions:
				latest_version = artifact.versions[0]
				active_artifact = {
					"artifact_id": str(artifact.id),
					"version_id": str(latest_version.id),
					"render_url": f"/api/v1/artifacts/{latest_version.id}/render",
					"download_url": f"/api/v1/artifacts/{latest_version.id}/download",
					"extension": latest_version.plan_json.get("artifact_extension", "html") if hasattr(latest_version, "plan_json") and isinstance(latest_version.plan_json, dict) else "html",
					"title": artifact.title or "Interactive artifact",
				}

		steps.append({
			"node": node,
			"label": label,
			"status": "done",
			"isOpen": False,
			"content": content,
			"sources": [],
		})

	trace_payload = {"steps": steps, "answer": answer}
	if active_artifact:
		trace_payload["artifact"] = active_artifact

	return trace_payload



@router.post("")
async def chat(request: Request, payload: ChatRequest) -> dict:
	service = _chat_service_from_request(request)

	try:
		result = await service.handle_message(
			user_id=payload.user_id,
			project_id=payload.project_id,
			user_query=payload.query,
			mode=payload.mode,
			conversation_id=payload.conversation_id,
		)
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc

	return {
		"conversation_id": str(result.conversation_id),
		"answer": result.answer,
		"approved": result.approved,
		"route_reason": result.route_reason,
		"iteration_count": result.iteration_count,
		"raw_state": result.raw_state,
	}


@router.post("/stream")
async def chat_stream(request: Request, payload: ChatRequest):
	service = _chat_service_from_request(request)
	
	tavily_api_key = request.headers.get("x-tavily-api-key")
	provider_api_key = request.headers.get("x-provider-api-key")
	provider_model = request.headers.get("x-provider-model")

	async def event_generator():
		try:
			stream_iter = service.stream_message(
				user_id=payload.user_id, 
				project_id=payload.project_id, 
				user_query=payload.clean_query, 
				mode=payload.mode, 
				conversation_id=payload.conversation_id,
				tavily_api_key=tavily_api_key,
				provider_api_key=provider_api_key,
				provider_model=provider_model,
				wants_artifact=payload.wants_artifact,
			)
			next_event_task = asyncio.create_task(anext(stream_iter))
			while True:
				done, pending = await asyncio.wait([next_event_task], timeout=15.0)
				if next_event_task in done:
					try:
						event = next_event_task.result()
						event_payload = json.dumps(event, default=str)
						yield f"data: {event_payload}\n\n"
						next_event_task = asyncio.create_task(anext(stream_iter))
					except StopAsyncIteration:
						break
				else:
					yield ": keepalive\n\n"
		except asyncio.CancelledError:
			logger.info(f"Stream cancelled by client (conversation_id={payload.conversation_id})")
			return
		except Exception as exc:
			logger.exception("Error during chat stream")
			err = {"type": "error", "detail": str(exc)}
			yield f"data: {json.dumps(err)}\n\n"

	return StreamingResponse(
		event_generator(), 
		media_type="text/event-stream",
		headers={
			"Cache-Control": "no-cache, no-transform",
			"Connection": "keep-alive",
			"X-Accel-Buffering": "no",
		}
	)

