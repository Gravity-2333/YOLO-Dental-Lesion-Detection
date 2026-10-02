from __future__ import annotations

from types import ModuleType, SimpleNamespace


def bind_model_and_storage_events(c: SimpleNamespace, h: ModuleType) -> None:
    """Bind model selection and local storage controls."""
    h.gr.on(
        triggers=[c.refresh_model_btn.click, c.show_advanced_models.input],
        fn=h.refresh_model_choices,
        inputs=[c.model_dir, c.model_file_select, c.show_advanced_models],
        outputs=[c.model_file_select, c.model_feedback],
        concurrency_limit=1,
        concurrency_id=h.MODEL_SCAN_CONCURRENCY_ID,
        trigger_mode="always_last",
        show_progress="minimal",
    )
    c.open_model_dir_btn.click(
        fn=h.choose_model_dir,
        inputs=[c.model_dir, c.model_file_select, c.show_advanced_models],
        outputs=[c.model_dir, c.model_file_select, c.model_feedback],
        queue=False,
        show_progress="hidden",
    )
    apply_selected_model_event = c.apply_model_btn.click(
        fn=h.apply_selected_model,
        inputs=[c.model_file_select, c.model_apply_target],
        outputs=[
            c.primary_model_path,
            c.compare_model_path,
            c.model_cards_view,
            c.model_info_markdown,
            c.model_feedback,
        ],
        concurrency_limit=1,
        concurrency_id=h.MODEL_SCAN_CONCURRENCY_ID,
        trigger_mode="always_last",
        show_progress="minimal",
    ).success(
        fn=h._workbench_model_status_html,
        inputs=[c.primary_model_path, c.device_choice],
        outputs=c.workbench_model_status,
        trigger_mode="always_last",
        queue=False,
        show_progress="hidden",
    )
    c.chain_detection_result_reset(apply_selected_model_event)

    apply_model_card_event = c.apply_model_card_btn.click(
        fn=h.apply_model_card,
        inputs=[
            c.model_card_select,
            c.model_apply_target,
            c.model_dir,
            c.show_advanced_models,
        ],
        outputs=[
            c.primary_model_path,
            c.compare_model_path,
            c.model_file_select,
            c.model_cards_view,
            c.model_info_markdown,
            c.model_feedback,
        ],
        concurrency_limit=1,
        concurrency_id=h.MODEL_SCAN_CONCURRENCY_ID,
        trigger_mode="always_last",
        show_progress="minimal",
    ).success(
        fn=h._workbench_model_status_html,
        inputs=[c.primary_model_path, c.device_choice],
        outputs=c.workbench_model_status,
        trigger_mode="always_last",
        queue=False,
        show_progress="hidden",
    )
    c.chain_detection_result_reset(apply_model_card_event)

    c.test_model_btn.click(
        fn=h.test_model_file,
        inputs=[c.primary_model_path, c.compare_model_path, c.settings_model_mode],
        outputs=c.model_feedback,
        concurrency_limit=1,
        concurrency_id=h.INFERENCE_CONCURRENCY_ID,
        trigger_mode="always_last",
        show_progress="minimal",
    )
    c.default_storage_btn.click(
        fn=h.default_storage_dir,
        outputs=[c.storage_dir, c.settings_feedback],
        queue=False,
        show_progress="hidden",
    )
    c.open_storage_btn.click(
        fn=h.choose_storage_dir,
        inputs=c.storage_dir,
        outputs=[c.storage_dir, c.settings_feedback],
        queue=False,
        show_progress="hidden",
    )
