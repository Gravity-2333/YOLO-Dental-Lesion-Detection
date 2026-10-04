from __future__ import annotations

from types import ModuleType, SimpleNamespace


def bind_export_and_record_events(c: SimpleNamespace, h: ModuleType) -> None:
    """Bind exports, case records, history, and report-center actions."""
    chat_export_event = c.export_btn.click(
        fn=h.export_chat_workspace,
        inputs=[c.chat_state, c.storage_dir, c.patient_select],
        outputs=[
            c.export_file,
            c.export_path,
            c.current_conversation_file_state,
            c.conversation_title_input,
        ],
        concurrency_limit=1,
        concurrency_id=h.EXPORT_CONCURRENCY_ID,
        show_progress="minimal",
    )
    chat_export_event.success(
        fn=h.refresh_conversation_history_with_selection,
        inputs=[
            c.storage_dir,
            c.patient_select,
            c.current_conversation_file_state,
        ],
        outputs=[c.conversation_select, c.conversation_feedback],
        trigger_mode="always_last",
        show_progress="minimal",
    )
    c.export_batch_btn.click(
        fn=h.export_batch_results_with_feedback,
        inputs=[c.batch_state, c.storage_dir],
        outputs=[c.batch_export_file, c.batch_export_path, c.batch_state],
        concurrency_limit=1,
        concurrency_id=h.EXPORT_CONCURRENCY_ID,
        show_progress="minimal",
    )
    c.export_batch_word_btn.click(
        fn=h.export_batch_word_report_with_feedback,
        inputs=[c.batch_state, c.storage_dir],
        outputs=[c.batch_word_file, c.batch_word_path, c.batch_state],
        concurrency_limit=1,
        concurrency_id=h.EXPORT_CONCURRENCY_ID,
        show_progress="minimal",
    )
    word_export_event = c.export_word_btn.click(
        fn=h.export_word_report_with_feedback,
        inputs=[c.batch_state, c.batch_select, c.storage_dir],
        outputs=[
            c.word_report_file,
            c.word_report_path,
            c.batch_state,
            c.report_export_status,
            c.open_word_report_dir_btn,
        ],
        concurrency_limit=1,
        concurrency_id=h.EXPORT_CONCURRENCY_ID,
        show_progress="minimal",
    )
    c.open_word_report_dir_btn.click(
        fn=h.open_report_location,
        inputs=[c.word_report_path, c.storage_dir],
        show_progress="hidden",
    )
    c.download_result_btn.click(
        fn=h.download_result_image_with_feedback,
        inputs=[c.batch_state, c.batch_select, c.storage_dir],
        outputs=[c.result_image_file, c.result_image_path, c.report_export_status],
        concurrency_limit=1,
        concurrency_id=h.EXPORT_CONCURRENCY_ID,
        show_progress="minimal",
    )
    zip_export_event = c.export_report_btn.click(
        fn=h.export_zip_report_with_feedback,
        inputs=[c.batch_state, c.batch_select, c.storage_dir],
        outputs=[
            c.report_file,
            c.report_path,
            c.batch_state,
            c.report_export_status,
            c.open_report_dir_btn,
        ],
        concurrency_limit=1,
        concurrency_id=h.EXPORT_CONCURRENCY_ID,
        show_progress="minimal",
    )
    c.open_report_dir_btn.click(
        fn=h.open_report_location,
        inputs=[c.report_path, c.storage_dir],
        show_progress="hidden",
    )
    c.save_case_btn.click(
        fn=h.save_case_record,
        inputs=[
            c.batch_state,
            c.batch_select,
            c.case_id,
            c.case_note,
            c.storage_dir,
        ],
        outputs=[
            c.case_feedback,
            c.case_select,
            c.case_table,
            c.case_detail,
            c.case_report_file,
            c.case_report_path,
        ],
        concurrency_limit=1,
        concurrency_id=h.RECORD_WRITE_CONCURRENCY_ID,
        show_progress="minimal",
    )
    c.refresh_case_btn.click(
        fn=h.refresh_case_records,
        inputs=[c.storage_dir, c.case_patient_select],
        outputs=c.case_list_outputs,
        trigger_mode="always_last",
        show_progress="minimal",
    )
    c.search_case_btn.click(
        fn=h.search_case_records_ui,
        inputs=[
            c.case_keyword,
            c.case_class_filter,
            c.case_level_filter,
            c.case_date_from,
            c.case_date_to,
            c.storage_dir,
            c.case_patient_select,
        ],
        outputs=c.case_list_outputs,
        trigger_mode="always_last",
        show_progress="minimal",
    )
    c.delete_case_btn.click(
        fn=h.delete_selected_case_record,
        inputs=[
            c.case_select,
            c.case_keyword,
            c.case_class_filter,
            c.case_level_filter,
            c.case_date_from,
            c.case_date_to,
            c.storage_dir,
            c.case_patient_select,
        ],
        outputs=[
            c.case_select,
            c.case_table,
            c.case_feedback,
            c.case_detail,
            c.case_report_file,
            c.case_report_path,
        ],
        concurrency_limit=1,
        concurrency_id=h.RECORD_WRITE_CONCURRENCY_ID,
        show_progress="minimal",
    )
    c.export_case_btn.click(
        fn=h.export_selected_case_record_with_feedback,
        inputs=[c.case_select, c.storage_dir, c.case_patient_select],
        outputs=[c.case_report_file, c.case_report_path],
        concurrency_limit=1,
        concurrency_id=h.EXPORT_CONCURRENCY_ID,
        show_progress="minimal",
    )
    c.case_select.input(
        fn=h.load_case_record_and_clear_export,
        inputs=[c.case_select, c.storage_dir, c.case_patient_select],
        outputs=[c.case_detail, c.case_report_file, c.case_report_path],
        trigger_mode="always_last",
        show_progress="minimal",
    )
    c.case_select.change(
        fn=h.record_action_button_state,
        inputs=c.case_select,
        outputs=[c.delete_case_btn, c.export_case_btn],
        queue=False,
        show_progress="hidden",
    )
    c.refresh_history_btn.click(
        fn=h.refresh_history_records,
        inputs=[c.storage_dir, c.history_patient_select],
        outputs=c.history_list_outputs,
        trigger_mode="always_last",
        show_progress="minimal",
    ).then(
        fn=h.reset_history_delete_confirmation,
        outputs=[c.delete_history_btn, c.history_delete_confirmation],
        queue=False,
        show_progress="hidden",
    )
    c.history_select.input(
        fn=h.load_history_record,
        inputs=[c.history_select, c.storage_dir, c.history_patient_select],
        outputs=c.history_detail,
        trigger_mode="always_last",
        show_progress="minimal",
    ).then(
        fn=h.reset_history_delete_confirmation,
        outputs=[c.delete_history_btn, c.history_delete_confirmation],
        queue=False,
        show_progress="hidden",
    )
    c.history_select.change(
        fn=h.record_action_button_state,
        inputs=c.history_select,
        outputs=[c.delete_history_btn, c.clear_history_btn],
        queue=False,
        show_progress="hidden",
    )
    c.delete_history_btn.click(
        fn=h.confirm_delete_selected_history_record,
        inputs=[
            c.history_select,
            c.storage_dir,
            c.history_patient_select,
            c.history_delete_confirmation,
        ],
        outputs=[
            *c.history_list_outputs,
            c.delete_history_btn,
            c.history_delete_confirmation,
        ],
        concurrency_limit=1,
        concurrency_id=h.RECORD_WRITE_CONCURRENCY_ID,
        show_progress="minimal",
    )
    c.clear_history_btn.click(
        fn=h.clear_all_history_records,
        inputs=[
            c.storage_dir,
            c.history_patient_select,
            c.history_clear_confirmation,
        ],
        outputs=[
            *c.history_list_outputs,
            c.clear_history_btn,
            c.history_clear_confirmation,
        ],
        concurrency_limit=1,
        concurrency_id=h.RECORD_WRITE_CONCURRENCY_ID,
        show_progress="minimal",
    )
    c.report_center.refresh_button.click(
        fn=h.refresh_report_center,
        inputs=[c.storage_dir, c.history_patient_select],
        outputs=c.report_list_outputs,
        trigger_mode="always_last",
        show_progress="minimal",
    ).then(
        fn=h.reset_report_trash_confirmation,
        outputs=c.report_trash_confirmation,
        queue=False,
        show_progress="hidden",
    )
    c.report_center.report_select.input(
        fn=h.load_active_report_center_item,
        inputs=[
            c.report_center.report_select,
            c.storage_dir,
            c.history_patient_select,
        ],
        outputs=[
            c.report_center.report_detail,
            c.report_center.report_file,
            c.report_center.report_feedback,
            c.report_center.trash_button,
        ],
        trigger_mode="always_last",
        show_progress="minimal",
    ).then(
        fn=h.reset_report_trash_confirmation,
        outputs=c.report_trash_confirmation,
        queue=False,
        show_progress="hidden",
    )
    c.report_center.trash_button.click(
        fn=h.confirm_trash_report_center_item,
        inputs=[
            c.report_center.report_select,
            c.storage_dir,
            c.history_patient_select,
            c.report_trash_confirmation,
        ],
        outputs=[*c.report_list_outputs, c.report_trash_confirmation],
        concurrency_limit=1,
        concurrency_id=h.RECORD_WRITE_CONCURRENCY_ID,
        show_progress="minimal",
    )
