from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, status

from ..component_structure import (
    apply_component_structure_metadata,
    build_component_structure_document,
    build_failed_component_structure_document,
)
from ..database import json_dumps
from ..dsl_patch import (
    DSLPatchDocument,
    apply_dsl_patch,
    build_dsl_patch,
    build_failed_patch_document,
    validate_enhanced_dsl,
)
from ..dsl_factory import DslRegionAsset, build_deterministic_dsl
from ..errors import ApiError, success_response
from ..ocr import OCRDocument, build_failed_ocr_document, extract_ocr
from ..png_tools import PngMetadata, UnsupportedPngCropError, crop_png, is_png, plan_regions, read_png_metadata
from ..state import state
from ..text_binding import (
    TextPrimitiveBindingDocument,
    apply_text_binding_metadata,
    build_failed_text_binding_document,
    build_text_binding_document,
)
from ..text_replacement import (
    TextReplacementDocument,
    apply_text_replacements,
    build_failed_text_replacement_document,
    build_text_replacement_document,
    normalize_replacement_mode,
)
from ..visual_primitives import (
    PrimitiveRegionInput,
    VisualPrimitiveDocument,
    build_failed_primitive_document,
    extract_visual_primitives,
)

router = APIRouter(prefix="/api")


@router.post("/upload")
async def upload_png(file: UploadFile = File(...)) -> dict[str, object]:
    task_id: str | None = None
    try:
        data = await file.read()
        if len(data) > state.settings.max_upload_bytes:
            raise ApiError(
                "FILE_TOO_LARGE",
                "PNG file is too large.",
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                stage="upload",
            )

        if file.content_type != "image/png" or not is_png(data):
            raise ApiError(
                "INVALID_FILE_TYPE",
                "Only PNG uploads are supported.",
                status_code=status.HTTP_400_BAD_REQUEST,
                stage="upload",
            )

        image = read_png_metadata(data)
        if image is None:
            raise ApiError(
                "INVALID_IMAGE_DIMENSIONS",
                "PNG image dimensions could not be read.",
                status_code=status.HTTP_400_BAD_REQUEST,
                stage="upload",
            )

        task_id = f"task_{secrets.token_hex(6)}"
        now = datetime.now(UTC).isoformat()
        upload_path = state.storage.save_upload(task_id, data)
        banner_path = state.storage.create_banner_asset(task_id, upload_path)
        region_assets, quality_flags = create_region_assets(task_id, data, image)
        region_inputs = create_region_inputs(task_id, image, region_assets, str(banner_path))
        base_dsl = build_deterministic_dsl(
            task_id=task_id,
            original_url=state.storage.original_url(task_id),
            fallback_url=state.storage.banner_url(task_id),
            image=image,
            regions=region_assets,
            quality_flags=quality_flags,
        )
        state.storage.base_dsl_path(task_id).write_text(json.dumps(base_dsl, ensure_ascii=False, indent=2), encoding="utf-8")

        state.database.insert_task(
            {
                "id": task_id,
                "status": "completed",
                "stage": "completed",
                "progress": 100,
                "message": "Deterministic DSL is ready.",
                "original_filename": file.filename or "upload.png",
                "mime_type": file.content_type or "image/png",
                "file_size": len(data),
                "upload_path": str(upload_path),
                "created_at": now,
                "updated_at": now,
                "completed_at": now,
                "failed_at": None,
            }
        )
        state.database.insert_asset(
            {
                "asset_id": "asset_original",
                "task_id": task_id,
                "role": "original",
                "path": str(upload_path),
                "url": state.storage.original_url(task_id),
                "mime_type": "image/png",
                "width": image.width,
                "height": image.height,
                "created_at": now,
            }
        )
        state.database.insert_asset(
            {
                "asset_id": "asset_banner",
                "task_id": task_id,
                "role": "fallback_region",
                "path": str(banner_path),
                "url": state.storage.banner_url(task_id),
                "mime_type": "image/png",
                "width": image.width,
                "height": image.height,
                "created_at": now,
            }
        )
        for region_asset in region_assets:
            state.database.insert_asset(
                {
                    "asset_id": region_asset.asset_id,
                    "task_id": task_id,
                    "role": "fallback_region",
                    "path": str(state.storage.region_path(task_id, region_asset.name)),
                    "url": region_asset.url,
                    "mime_type": "image/png",
                    "width": region_asset.width,
                    "height": region_asset.height,
                    "created_at": now,
                }
            )
        primitive_document = save_primitive_result(task_id, image, region_assets, region_inputs, now)
        ocr_document = save_ocr_result(task_id, image, upload_path, now)
        patched_dsl = save_dsl_patch_result(task_id, base_dsl, ocr_document, primitive_document, now)
        replacement_document, replaced_dsl = save_text_replacement_result(task_id, image, data, ocr_document, patched_dsl, now)
        binding_document, bound_dsl = save_text_binding_result(
            task_id,
            image,
            ocr_document,
            primitive_document,
            replacement_document,
            replaced_dsl,
            now,
        )
        final_dsl = save_component_structure_result(
            task_id,
            image,
            ocr_document,
            primitive_document,
            replacement_document,
            binding_document,
            bound_dsl,
            now,
        )
        dsl_path = state.storage.dsl_path(task_id)
        dsl_path.write_text(json.dumps(final_dsl, ensure_ascii=False, indent=2), encoding="utf-8")
        state.database.insert_dsl_result(
            {
                "task_id": task_id,
                "dsl_path": str(dsl_path),
                "version": "0.1",
                "validation_status": "valid",
                "validation_errors": json_dumps([]),
                "created_at": now,
            }
        )

        return success_response(
            {
                "taskId": task_id,
                "status": "completed",
                "stage": "completed",
                "progress": 100,
                "file": {
                    "filename": file.filename or "upload.png",
                    "mimeType": file.content_type or "image/png",
                    "size": len(data),
                },
            }
        )
    except ApiError:
        raise
    except Exception as error:
        state.database.insert_error(
            task_id=task_id,
            stage="upload",
            error_code="UPLOAD_FAILED",
            message="Upload failed.",
            detail=str(error),
        )
        raise ApiError(
            "UPLOAD_FAILED",
            "Upload failed.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            stage="upload",
            task_id=task_id,
            detail=str(error),
        ) from error


def create_region_assets(task_id: str, data: bytes, image: PngMetadata) -> tuple[list[DslRegionAsset], list[str]]:
    regions = plan_regions(image)
    if len(regions) == 1 and regions[0].name == "full_image":
        return [], []

    try:
        cropped_regions = [(region, crop_png(data, region)) for region in regions]
    except UnsupportedPngCropError:
        return [], ["region_crop_unsupported"]

    assets: list[DslRegionAsset] = []
    for region, cropped in cropped_regions:
        state.storage.save_region_asset(task_id, region.name, cropped)
        assets.append(
            DslRegionAsset(
                asset_id=f"asset_region_{region.name}",
                name=region.name,
                url=state.storage.region_url(task_id, region.name),
                x=region.x,
                y=region.y,
                width=region.width,
                height=region.height,
            )
        )

    return assets, []


def create_region_inputs(
    task_id: str,
    image: PngMetadata,
    region_assets: list[DslRegionAsset],
    fallback_path: str,
) -> list[PrimitiveRegionInput]:
    if not region_assets:
        return [
            PrimitiveRegionInput(
                id="full_image",
                path=fallback_path,
                x=0,
                y=0,
                width=image.width,
                height=image.height,
            )
        ]
    return [
        PrimitiveRegionInput(
            id=region.name,
            path=str(state.storage.region_path(task_id, region.name)),
            x=region.x,
            y=region.y,
            width=region.width,
            height=region.height,
        )
        for region in region_assets
    ]


def save_primitive_result(
    task_id: str,
    image: PngMetadata,
    region_assets: list[DslRegionAsset],
    region_inputs: list[PrimitiveRegionInput],
    created_at: str,
) -> VisualPrimitiveDocument:
    failed_logged = False
    try:
        document = extract_visual_primitives(
            task_id=task_id,
            image=image,
            regions=region_assets,
            region_inputs=region_inputs,
            settings=state.settings,
        )
    except Exception as error:
        state.database.insert_error(
            task_id=task_id,
            stage="primitive_extract",
            error_code="PRIMITIVE_EXTRACTION_FAILED",
            message="Visual primitive extraction failed.",
            detail=str(error),
        )
        failed_logged = True
        document = build_failed_primitive_document(
            task_id=task_id,
            image=image,
            provider=state.settings.visual_primitive_provider,
            model=state.settings.openai_vision_model if state.settings.visual_primitive_provider == "openai" else None,
            code="PRIMITIVE_EXTRACTION_FAILED",
            message="Visual primitive extraction failed.",
        )
    if document.status == "failed" and not failed_logged:
        state.database.insert_error(
            task_id=task_id,
            stage="primitive_extract",
            error_code=document.error["code"] if document.error else "PRIMITIVE_EXTRACTION_FAILED",
            message=document.error["message"] if document.error else "Visual primitive extraction failed.",
            detail=json_dumps([warning.__dict__ for warning in document.warnings]),
        )

    primitive_path = state.storage.save_primitives(
        task_id,
        json_dumps(document.to_dict()),
    )
    state.database.insert_primitive_result(
        {
            "task_id": task_id,
            "provider": document.provider,
            "model": document.model,
            "status": document.status,
            "primitive_path": str(primitive_path),
            "primitive_count": len(document.primitives),
            "relation_count": len(document.relations),
            "error_code": document.error["code"] if document.error else None,
            "error_message": document.error["message"] if document.error else None,
            "created_at": created_at,
        }
    )
    return document


def save_ocr_result(task_id: str, image: PngMetadata, source_path: Path, created_at: str) -> OCRDocument:
    failed_logged = False
    try:
        document = extract_ocr(task_id=task_id, image=image, settings=state.settings, source_path=source_path)
    except Exception as error:
        state.database.insert_error(
            task_id=task_id,
            stage="ocr_extract",
            error_code="OCR_EXTRACTION_FAILED",
            message="OCR extraction failed.",
            detail=str(error),
        )
        failed_logged = True
        document = build_failed_ocr_document(
            task_id=task_id,
            image=image,
            provider=state.settings.ocr_provider,
            model=None,
            code="OCR_EXTRACTION_FAILED",
            message="OCR extraction failed.",
        )
    if document.status == "failed" and not failed_logged:
        state.database.insert_error(
            task_id=task_id,
            stage="ocr_extract",
            error_code=document.error["code"] if document.error else "OCR_EXTRACTION_FAILED",
            message=document.error["message"] if document.error else "OCR extraction failed.",
            detail=json_dumps([warning.__dict__ for warning in document.warnings]),
        )

    ocr_path = state.storage.save_ocr(task_id, json_dumps(document.to_dict()))
    state.database.insert_ocr_result(
        {
            "task_id": task_id,
            "provider": document.provider,
            "model": document.model,
            "status": document.status,
            "ocr_path": str(ocr_path),
            "block_count": len(document.blocks),
            "error_code": document.error["code"] if document.error else None,
            "error_message": document.error["message"] if document.error else None,
            "created_at": created_at,
        }
    )
    return document


def save_dsl_patch_result(
    task_id: str,
    base_dsl: dict[str, object],
    ocr_document: OCRDocument,
    primitive_document: VisualPrimitiveDocument,
    created_at: str,
) -> dict[str, object]:
    mode = state.settings.dsl_patch_mode
    failed_logged = False
    try:
        if ocr_document.status == "failed":
            document = build_failed_patch_document(
                task_id=task_id,
                mode=mode,
                code="OCR_EXTRACTION_FAILED",
                message="DSL patch skipped because OCR extraction failed.",
            )
            final_dsl = base_dsl
        else:
            document = build_dsl_patch(
                base_dsl=base_dsl,
                ocr_document=ocr_document,
                primitive_document=primitive_document,
                mode=mode,
            )
            final_dsl = apply_dsl_patch(base_dsl, document)
            validation_errors = validate_enhanced_dsl(final_dsl)
            if validation_errors:
                state.database.insert_error(
                    task_id=task_id,
                    stage="dsl_patch_validate",
                    error_code="DSL_PATCH_VALIDATION_FAILED",
                    message="DSL patch validation failed.",
                    detail=json_dumps(validation_errors),
                )
                failed_logged = True
                document = build_failed_patch_document(
                    task_id=task_id,
                    mode=mode,
                    code="DSL_PATCH_VALIDATION_FAILED",
                    message="DSL patch validation failed.",
                )
                final_dsl = base_dsl
    except Exception as error:
        state.database.insert_error(
            task_id=task_id,
            stage="dsl_patch_build",
            error_code="DSL_PATCH_BUILD_FAILED",
            message="DSL patch build failed.",
            detail=str(error),
        )
        failed_logged = True
        document = build_failed_patch_document(
            task_id=task_id,
            mode=mode,
            code="DSL_PATCH_BUILD_FAILED",
            message="DSL patch build failed.",
        )
        final_dsl = base_dsl

    if document.status == "failed" and not failed_logged:
        state.database.insert_error(
            task_id=task_id,
            stage="dsl_patch_build",
            error_code=document.error["code"] if document.error else "DSL_PATCH_BUILD_FAILED",
            message=document.error["message"] if document.error else "DSL patch build failed.",
            detail=json_dumps([warning.__dict__ for warning in document.warnings]),
        )

    patch_path = state.storage.save_patch(task_id, json_dumps(document.to_dict()))
    state.database.insert_dsl_patch_result(
        {
            "task_id": task_id,
            "mode": document.mode,
            "status": document.status,
            "patch_path": str(patch_path),
            "patch_count": len(document.patches),
            "warning_count": len(document.warnings),
            "error_code": document.error["code"] if document.error else None,
            "error_message": document.error["message"] if document.error else None,
            "created_at": created_at,
        }
    )
    return final_dsl


def save_text_replacement_result(
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    ocr_document: OCRDocument,
    input_dsl: dict[str, object],
    created_at: str,
) -> tuple[TextReplacementDocument, dict[str, object]]:
    mode = normalize_replacement_mode(state.settings.text_replacement_mode)
    if mode == "off":
        document = build_failed_text_replacement_document(
            task_id=task_id,
            image=image,
            mode=mode,
            code="TEXT_REPLACEMENT_NOT_ENABLED",
            message="Text replacement is disabled.",
        )
        return document, input_dsl

    failed_logged = False
    try:
        document = build_text_replacement_document(
            task_id=task_id,
            image=image,
            png_data=png_data,
            ocr_document=ocr_document,
            settings=state.settings,
        )
        final_dsl = apply_text_replacements(input_dsl, document, ocr_document)
        validation_errors = validate_enhanced_dsl(final_dsl)
        if validation_errors:
            state.database.insert_error(
                task_id=task_id,
                stage="text_replacement_validate",
                error_code="TEXT_REPLACEMENT_VALIDATION_FAILED",
                message="Text replacement validation failed.",
                detail=json_dumps(validation_errors),
            )
            failed_logged = True
            document = build_failed_text_replacement_document(
                task_id=task_id,
                image=image,
                mode=mode,
                code="TEXT_REPLACEMENT_VALIDATION_FAILED",
                message="Text replacement validation failed.",
            )
            final_dsl = input_dsl
    except Exception as error:
        state.database.insert_error(
            task_id=task_id,
            stage="text_replacement",
            error_code="TEXT_REPLACEMENT_FAILED",
            message="Text replacement failed.",
            detail=str(error),
        )
        failed_logged = True
        document = build_failed_text_replacement_document(
            task_id=task_id,
            image=image,
            mode=mode,
            code="TEXT_REPLACEMENT_FAILED",
            message="Text replacement failed.",
        )
        final_dsl = input_dsl

    if document.status == "failed" and not failed_logged:
        state.database.insert_error(
            task_id=task_id,
            stage="text_replacement",
            error_code=document.error["code"] if document.error else "TEXT_REPLACEMENT_FAILED",
            message=document.error["message"] if document.error else "Text replacement failed.",
            detail=json_dumps([warning.__dict__ for warning in document.warnings]),
        )

    replacement_path = state.storage.save_text_replacement(task_id, json_dumps(document.to_dict()))
    accepted_count = sum(1 for decision in document.decisions if decision.decision == "accepted")
    rejected_count = sum(1 for decision in document.decisions if decision.decision == "rejected")
    state.database.insert_text_replacement_result(
        {
            "task_id": task_id,
            "mode": document.mode,
            "status": document.status,
            "replacement_path": str(replacement_path),
            "accepted_count": accepted_count,
            "rejected_count": rejected_count,
            "warning_count": len(document.warnings),
            "error_code": document.error["code"] if document.error else None,
            "error_message": document.error["message"] if document.error else None,
            "created_at": created_at,
        }
    )
    return document, final_dsl


def save_text_binding_result(
    task_id: str,
    image: PngMetadata,
    ocr_document: OCRDocument,
    primitive_document: VisualPrimitiveDocument,
    replacement_document: TextReplacementDocument,
    input_dsl: dict[str, object],
    created_at: str,
) -> tuple[TextPrimitiveBindingDocument, dict[str, object]]:
    if not state.settings.text_binding_enabled:
        document = build_failed_text_binding_document(
            task_id=task_id,
            image=image,
            code="TEXT_BINDING_NOT_ENABLED",
            message="Text binding is disabled.",
        )
        return document, input_dsl

    failed_logged = False
    try:
        document = build_text_binding_document(
            task_id=task_id,
            image=image,
            ocr_document=ocr_document,
            primitive_document=primitive_document,
            replacement_document=replacement_document,
            dsl=input_dsl,
            settings=state.settings,
        )
        final_dsl = apply_text_binding_metadata(input_dsl, document)
        validation_errors = validate_enhanced_dsl(final_dsl)
        if validation_errors:
            state.database.insert_error(
                task_id=task_id,
                stage="text_binding",
                error_code="TEXT_BINDING_VALIDATION_FAILED",
                message="Text binding validation failed.",
                detail=json_dumps(validation_errors),
            )
            failed_logged = True
            document = build_failed_text_binding_document(
                task_id=task_id,
                image=image,
                code="TEXT_BINDING_VALIDATION_FAILED",
                message="Text binding validation failed.",
            )
            final_dsl = input_dsl
    except Exception as error:
        state.database.insert_error(
            task_id=task_id,
            stage="text_binding",
            error_code="TEXT_BINDING_FAILED",
            message="Text binding failed.",
            detail=str(error),
        )
        failed_logged = True
        document = build_failed_text_binding_document(
            task_id=task_id,
            image=image,
            code="TEXT_BINDING_FAILED",
            message="Text binding failed.",
        )
        final_dsl = input_dsl

    if document.status == "failed" and not failed_logged:
        state.database.insert_error(
            task_id=task_id,
            stage="text_binding",
            error_code=document.error["code"] if document.error else "TEXT_BINDING_FAILED",
            message=document.error["message"] if document.error else "Text binding failed.",
            detail=json_dumps([warning.__dict__ for warning in document.warnings]),
        )

    binding_path = state.storage.save_text_binding(task_id, json_dumps(document.to_dict()))
    state.database.insert_text_binding_result(
        {
            "task_id": task_id,
            "status": document.status,
            "binding_path": str(binding_path),
            "container_count": len(document.containers),
            "binding_count": len(document.bindings),
            "unbound_count": len(document.unboundTextIds),
            "warning_count": len(document.warnings),
            "error_code": document.error["code"] if document.error else None,
            "error_message": document.error["message"] if document.error else None,
            "created_at": created_at,
        }
    )
    return document, final_dsl


def save_component_structure_result(
    task_id: str,
    image: PngMetadata,
    ocr_document: OCRDocument,
    primitive_document: VisualPrimitiveDocument,
    replacement_document: TextReplacementDocument,
    binding_document: TextPrimitiveBindingDocument,
    input_dsl: dict[str, object],
    created_at: str,
) -> dict[str, object]:
    if not state.settings.component_structure_enabled:
        return input_dsl

    failed_logged = False
    try:
        document = build_component_structure_document(
            task_id=task_id,
            image=image,
            ocr_document=ocr_document,
            primitive_document=primitive_document,
            replacement_document=replacement_document,
            binding_document=binding_document,
            dsl=input_dsl,
            settings=state.settings,
        )
        final_dsl = apply_component_structure_metadata(input_dsl, document)
        validation_errors = validate_enhanced_dsl(final_dsl)
        if validation_errors:
            state.database.insert_error(
                task_id=task_id,
                stage="component_structure",
                error_code="COMPONENT_STRUCTURE_VALIDATION_FAILED",
                message="Component structure validation failed.",
                detail=json_dumps(validation_errors),
            )
            failed_logged = True
            document = build_failed_component_structure_document(
                task_id=task_id,
                image=image,
                code="COMPONENT_STRUCTURE_VALIDATION_FAILED",
                message="Component structure validation failed.",
            )
            final_dsl = input_dsl
    except Exception as error:
        state.database.insert_error(
            task_id=task_id,
            stage="component_structure",
            error_code="COMPONENT_STRUCTURE_FAILED",
            message="Component structure failed.",
            detail=str(error),
        )
        failed_logged = True
        document = build_failed_component_structure_document(
            task_id=task_id,
            image=image,
            code="COMPONENT_STRUCTURE_FAILED",
            message="Component structure failed.",
        )
        final_dsl = input_dsl

    if document.status == "failed" and not failed_logged:
        state.database.insert_error(
            task_id=task_id,
            stage="component_structure",
            error_code=document.error["code"] if document.error else "COMPONENT_STRUCTURE_FAILED",
            message=document.error["message"] if document.error else "Component structure failed.",
            detail=json_dumps([warning.__dict__ for warning in document.warnings]),
        )

    structure_path = state.storage.save_component_structure(task_id, json_dumps(document.to_dict()))
    state.database.insert_component_structure_result(
        {
            "task_id": task_id,
            "status": document.status,
            "structure_path": str(structure_path),
            "component_count": len(document.components),
            "group_count": len(document.groups),
            "unstructured_count": len(document.unstructuredContainerIds),
            "warning_count": len(document.warnings),
            "error_code": document.error["code"] if document.error else None,
            "error_message": document.error["message"] if document.error else None,
            "created_at": created_at,
        }
    )
    return final_dsl
