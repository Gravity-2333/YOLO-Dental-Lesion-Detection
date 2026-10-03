from __future__ import annotations

from types import ModuleType, SimpleNamespace


def bind_workspace_events(c: SimpleNamespace, h: ModuleType) -> None:
    """Bind patient, inference, result, and settings workflows."""
    AI_REQUEST_CONCURRENCY_ID = h.AI_REQUEST_CONCURRENCY_ID
    INFERENCE_CONCURRENCY_ID = h.INFERENCE_CONCURRENCY_ID
    RECORD_WRITE_CONCURRENCY_ID = h.RECORD_WRITE_CONCURRENCY_ID
    RESULT_RESET_CONCURRENCY_ID = h.RESULT_RESET_CONCURRENCY_ID
    RESULT_VIEW_CONCURRENCY_ID = h.RESULT_VIEW_CONCURRENCY_ID
    _example_preview_text = h._example_preview_text
    _workbench_model_status_html = h._workbench_model_status_html
    active_detection_conversation = h.active_detection_conversation
    add_patient_profile = h.add_patient_profile
    analysis_button_state = h.analysis_button_state
    archive_patient_profile = h.archive_patient_profile
    clear_outputs = h.clear_outputs
    clear_outputs_with_quality = h.clear_outputs_with_quality
    clear_patient_session = h.clear_patient_session
    clear_session_after_storage_change = h.clear_session_after_storage_change
    gr = h.gr
    lazy_refresh_case_records = h.lazy_refresh_case_records
    lazy_refresh_history_page = h.lazy_refresh_history_page
    load_demo_example = h.load_demo_example
    load_tab_report_center_file = h.load_tab_report_center_file
    on_enable_compare_change = h.on_enable_compare_change
    refresh_ai_runtime_status = h.refresh_ai_runtime_status
    refresh_ai_tab_content = h.refresh_ai_tab_content
    refresh_conversations_after_storage_change = h.refresh_conversations_after_storage_change
    refresh_patient_selection_choices = h.refresh_patient_selection_choices
    refresh_report_center_after_storage_change = h.refresh_report_center_after_storage_change
    restore_patient_profile = h.restore_patient_profile
    run_batch_detection = h.run_batch_detection
    run_single_detection = h.run_single_detection
    save_ui_settings = h.save_ui_settings
    select_batch_item = h.select_batch_item
    set_api_key_mode = h.set_api_key_mode
    sync_model_mode = h.sync_model_mode
    sync_patient_selections_with_session_clear = h.sync_patient_selections_with_session_clear
    test_ai_settings = h.test_ai_settings
    toggle_ai_settings = h.toggle_ai_settings
    toggle_direct_key_visibility = h.toggle_direct_key_visibility
    toggle_summary = h.toggle_summary
    update_detection_visibility = h.update_detection_visibility
    update_patient_profile = h.update_patient_profile
    add_patient_btn = c.add_patient_btn
    advice_box = c.advice_box
    advice_style = c.advice_style
    ai_enabled = c.ai_enabled
    ai_group = c.ai_group
    ai_model = c.ai_model
    ai_runtime_status = c.ai_runtime_status
    ai_tab = c.ai_tab
    apply_model_btn = c.apply_model_btn
    apply_model_card_btn = c.apply_model_card_btn
    archive_patient_btn = c.archive_patient_btn
    archived_patient_select = c.archived_patient_select
    auto_save = c.auto_save
    base_url = c.base_url
    batch_btn = c.batch_btn
    batch_files = c.batch_files
    batch_select = c.batch_select
    batch_state = c.batch_state
    case_detail = c.case_detail
    case_feedback = c.case_feedback
    case_id = c.case_id
    case_list_outputs = c.case_list_outputs
    case_loaded_state = c.case_loaded_state
    case_note = c.case_note
    case_patient_select = c.case_patient_select
    case_report_file = c.case_report_file
    case_report_path = c.case_report_path
    case_select = c.case_select
    case_tab = c.case_tab
    case_table = c.case_table
    chain_detection_result_reset = c.chain_detection_result_reset
    chain_patient_workspace_refresh = c.chain_patient_workspace_refresh
    chat_input = c.chat_input
    chat_state = c.chat_state
    chatbot = c.chatbot
    clear_session_btn = c.clear_session_btn
    common_inputs = c.common_inputs
    common_outputs = c.common_outputs
    compare_model_path = c.compare_model_path
    comparison_section = c.comparison_section
    comparison_view = c.comparison_view
    conf = c.conf
    conversation_feedback = c.conversation_feedback
    conversation_loaded_state = c.conversation_loaded_state
    conversation_select = c.conversation_select
    conversation_title_input = c.conversation_title_input
    current_conversation_file_state = c.current_conversation_file_state
    custom_prompt = c.custom_prompt
    det_table = c.det_table
    device_choice = c.device_choice
    direct_api_key_hidden = c.direct_api_key_hidden
    direct_api_key_visible = c.direct_api_key_visible
    direct_key_visible = c.direct_key_visible
    download_result_btn = c.download_result_btn
    edit_patient_name = c.edit_patient_name
    edit_patient_reference = c.edit_patient_reference
    enable_compare = c.enable_compare
    env_api_key = c.env_api_key
    example_info = c.example_info
    example_select = c.example_select
    export_file = c.export_file
    export_path = c.export_path
    export_report_btn = c.export_report_btn
    export_word_btn = c.export_word_btn
    followup_click_action = c.followup_click_action
    followup_generation_enabled = c.followup_generation_enabled
    followup_generation_prompt = c.followup_generation_prompt
    history_detail = c.history_detail
    history_feedback = c.history_feedback
    history_limit = c.history_limit
    history_list_outputs = c.history_list_outputs
    history_loaded_state = c.history_loaded_state
    history_patient_select = c.history_patient_select
    history_select = c.history_select
    history_tab = c.history_tab
    history_table = c.history_table
    image = c.image
    iou = c.iou
    keep_followup_prompts = c.keep_followup_prompts
    key_mode = c.key_mode
    load_example_btn = c.load_example_btn
    model_dir = c.model_dir
    model_input_output = c.model_input_output
    model_mode = c.model_mode
    model_mode_feedback = c.model_mode_feedback
    magnifier_enabled = c.magnifier_enabled
    new_patient_name = c.new_patient_name
    new_patient_reference = c.new_patient_reference
    original_output = c.original_output
    patient_feedback = c.patient_feedback
    patient_refresh_id_state = c.patient_refresh_id_state
    patient_select = c.patient_select
    patient_session_outputs = c.patient_session_outputs
    primary_model_path = c.primary_model_path
    quality_box = c.quality_box
    report_center = c.report_center
    report_file = c.report_file
    report_file_target_state = c.report_file_target_state
    report_list_outputs = c.report_list_outputs
    report_metadata_outputs = c.report_metadata_outputs
    report_path = c.report_path
    report_export_menu_btn = c.report_export_menu_btn
    report_export_status = c.report_export_status
    restore_patient_btn = c.restore_patient_btn
    result_image_file = c.result_image_file
    result_image_path = c.result_image_path
    result_output = c.result_output
    run_btn = c.run_btn
    save_case_btn = c.save_case_btn
    save_history = c.save_history
    save_key = c.save_key
    save_patient_btn = c.save_patient_btn
    save_settings_btn = c.save_settings_btn
    settings = c.settings
    settings_feedback = c.settings_feedback
    settings_model_mode = c.settings_model_mode
    show_direct_key_btn = c.show_direct_key_btn
    show_summary = c.show_summary
    storage_changed_state = c.storage_changed_state
    storage_dir = c.storage_dir
    summary = c.summary
    task_max_tokens = c.task_max_tokens
    task_model = c.task_model
    task_temperature = c.task_temperature
    test_btn = c.test_btn
    test_result = c.test_result
    title_generation_mode = c.title_generation_mode
    title_generation_prompt = c.title_generation_prompt
    use_clahe = c.use_clahe
    visible_class_filter = c.visible_class_filter
    word_report_file = c.word_report_file
    word_report_path = c.word_report_path
    workbench_model_status = c.workbench_model_status

    # Lazy-load record stores when their tabs become visible. This keeps
    # startup and tab navigation responsive even with large local archives.
    patient_choice_outputs = [patient_select, case_patient_select, history_patient_select]
    ai_tab.select(
        fn=refresh_ai_tab_content,
        inputs=[
            conversation_loaded_state,
            storage_dir,
            patient_select,
            chat_state,
            batch_state,
            batch_select,
            *settings.ai_request_inputs(),
        ],
        outputs=[
            conversation_select,
            conversation_feedback,
            ai_runtime_status,
            conversation_loaded_state,
        ],
        trigger_mode="always_last",
        show_progress="minimal",
    )
    case_tab.select(
        fn=refresh_patient_selection_choices,
        inputs=[storage_dir, case_patient_select],
        outputs=patient_choice_outputs,
        trigger_mode="always_last",
        show_progress="hidden",
    ).success(
        fn=lazy_refresh_case_records,
        inputs=[case_loaded_state, storage_dir, case_patient_select],
        outputs=[*case_list_outputs, case_loaded_state],
        trigger_mode="always_last",
        show_progress="minimal",
    )
    history_tab.select(
        fn=refresh_patient_selection_choices,
        inputs=[storage_dir, history_patient_select],
        outputs=patient_choice_outputs,
        trigger_mode="always_last",
        show_progress="hidden",
    ).success(
        fn=lazy_refresh_history_page,
        inputs=[history_loaded_state, storage_dir, history_patient_select],
        outputs=[
            *history_list_outputs,
            *report_metadata_outputs,
            report_file_target_state,
            history_loaded_state,
        ],
        trigger_mode="always_last",
        show_progress="minimal",
    ).success(
        fn=load_tab_report_center_file,
        inputs=[report_file_target_state, storage_dir, history_patient_select],
        outputs=report_center.report_file,
        trigger_mode="always_last",
        show_progress="minimal",
    )

    clear_session_btn.click(
        fn=clear_patient_session,
        outputs=patient_session_outputs,
        queue=False,
        show_progress="hidden",
    )
    patient_select_event = patient_select.input(
        fn=sync_patient_selections_with_session_clear,
        inputs=patient_select,
        outputs=[
            case_patient_select,
            history_patient_select,
            *patient_session_outputs,
            patient_refresh_id_state,
        ],
        trigger_mode="always_last",
        show_progress="hidden",
    )
    chain_patient_workspace_refresh(
        patient_select_event,
        patient_refresh_id_state,
        session_cleared=True,
    )
    case_patient_select_event = case_patient_select.input(
        fn=sync_patient_selections_with_session_clear,
        inputs=case_patient_select,
        outputs=[
            patient_select,
            history_patient_select,
            *patient_session_outputs,
            patient_refresh_id_state,
        ],
        trigger_mode="always_last",
        show_progress="hidden",
    )
    chain_patient_workspace_refresh(
        case_patient_select_event,
        patient_refresh_id_state,
        session_cleared=True,
    )
    history_patient_select_event = history_patient_select.input(
        fn=sync_patient_selections_with_session_clear,
        inputs=history_patient_select,
        outputs=[
            patient_select,
            case_patient_select,
            *patient_session_outputs,
            patient_refresh_id_state,
        ],
        trigger_mode="always_last",
        show_progress="hidden",
    )
    chain_patient_workspace_refresh(
        history_patient_select_event,
        patient_refresh_id_state,
        session_cleared=True,
    )
    add_patient_event = add_patient_btn.click(
        fn=add_patient_profile,
        inputs=[new_patient_name, new_patient_reference, storage_dir],
        outputs=[
            patient_select,
            case_patient_select,
            history_patient_select,
            new_patient_name,
            new_patient_reference,
            patient_feedback,
            patient_refresh_id_state,
        ],
        concurrency_limit=1,
        concurrency_id=RECORD_WRITE_CONCURRENCY_ID,
        show_progress="minimal",
    )
    chain_patient_workspace_refresh(add_patient_event, patient_refresh_id_state)
    save_patient_btn.click(
        fn=update_patient_profile,
        inputs=[case_patient_select, edit_patient_name, edit_patient_reference, storage_dir],
        outputs=[
            patient_select,
            case_patient_select,
            history_patient_select,
            edit_patient_name,
            edit_patient_reference,
            archive_patient_btn,
            patient_feedback,
            patient_refresh_id_state,
        ],
        concurrency_limit=1,
        concurrency_id=RECORD_WRITE_CONCURRENCY_ID,
        show_progress="minimal",
    )
    archive_patient_event = archive_patient_btn.click(
        fn=archive_patient_profile,
        inputs=[case_patient_select, storage_dir],
        outputs=[
            patient_select,
            case_patient_select,
            history_patient_select,
            archived_patient_select,
            edit_patient_name,
            edit_patient_reference,
            archive_patient_btn,
            restore_patient_btn,
            patient_feedback,
            patient_refresh_id_state,
        ],
        concurrency_limit=1,
        concurrency_id=RECORD_WRITE_CONCURRENCY_ID,
        show_progress="minimal",
    )
    chain_patient_workspace_refresh(archive_patient_event, patient_refresh_id_state)
    restore_patient_event = restore_patient_btn.click(
        fn=restore_patient_profile,
        inputs=[archived_patient_select, storage_dir],
        outputs=[
            patient_select,
            case_patient_select,
            history_patient_select,
            archived_patient_select,
            edit_patient_name,
            edit_patient_reference,
            archive_patient_btn,
            restore_patient_btn,
            patient_feedback,
            patient_refresh_id_state,
        ],
        concurrency_limit=1,
        concurrency_id=RECORD_WRITE_CONCURRENCY_ID,
        show_progress="minimal",
    )
    chain_patient_workspace_refresh(restore_patient_event, patient_refresh_id_state)

    single_detection_event = run_btn.click(
        fn=run_single_detection,
        inputs=[image, *common_inputs],
        outputs=common_outputs,
        concurrency_limit=1,
        concurrency_id=INFERENCE_CONCURRENCY_ID,
        show_progress="minimal",
    )
    batch_detection_event = batch_btn.click(
        fn=run_batch_detection,
        inputs=[batch_files, *common_inputs],
        outputs=common_outputs,
        concurrency_limit=1,
        concurrency_id=INFERENCE_CONCURRENCY_ID,
        show_progress="minimal",
    )
    for detection_event in (single_detection_event, batch_detection_event):
        detection_event.success(
            fn=active_detection_conversation,
            inputs=[auto_save, storage_dir, patient_select, chat_state],
            outputs=[current_conversation_file_state, conversation_title_input],
            queue=False,
            show_progress="hidden",
        )
    inference_events = [single_detection_event, batch_detection_event]
    gr.on(
        triggers=[
            image.input,
            batch_files.upload,
            batch_files.clear,
            primary_model_path.input,
            compare_model_path.input,
            conf.input,
            iou.input,
            device_choice.input,
            use_clahe.input,
            model_mode.input,
            settings_model_mode.input,
            enable_compare.input,
            apply_model_btn.click,
            apply_model_card_btn.click,
            patient_select.input,
            case_patient_select.input,
            history_patient_select.input,
            add_patient_btn.click,
            archive_patient_btn.click,
            restore_patient_btn.click,
            clear_session_btn.click,
            save_settings_btn.click,
        ],
        fn=None,
        cancels=inference_events,
        queue=False,
        show_progress="hidden",
    )

    # User-only listeners avoid reprocessing when another callback updates a component.
    # This is important for large images and model outputs: Gradio's `.change()` also
    # fires for function updates, which can create duplicate redraws or event loops.
    image.input(
        fn=clear_outputs_with_quality,
        inputs=image,
        outputs=common_outputs,
        concurrency_limit=1,
        concurrency_id=RESULT_RESET_CONCURRENCY_ID,
        trigger_mode="always_last",
        show_progress="hidden",
    )
    batch_files.upload(
        fn=clear_outputs,
        outputs=common_outputs,
        concurrency_limit=1,
        concurrency_id=RESULT_RESET_CONCURRENCY_ID,
        trigger_mode="always_last",
        show_progress="hidden",
    )
    batch_files.clear(
        fn=clear_outputs,
        outputs=common_outputs,
        concurrency_limit=1,
        concurrency_id=RESULT_RESET_CONCURRENCY_ID,
        trigger_mode="always_last",
        show_progress="hidden",
    )
    image.change(
        fn=analysis_button_state,
        inputs=image,
        outputs=run_btn,
        queue=False,
        show_progress="hidden",
    )
    batch_files.change(
        fn=analysis_button_state,
        inputs=batch_files,
        outputs=batch_btn,
        queue=False,
        show_progress="hidden",
    )
    stale_result_controls = [primary_model_path, compare_model_path, conf, iou, device_choice, use_clahe]
    for control in stale_result_controls:
        control.input(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
            concurrency_limit=1,
            concurrency_id=RESULT_RESET_CONCURRENCY_ID,
            trigger_mode="always_last",
            show_progress="hidden",
        )
    gr.on(
        triggers=[primary_model_path.input, device_choice.input],
        fn=_workbench_model_status_html,
        inputs=[primary_model_path, device_choice],
        outputs=workbench_model_status,
        trigger_mode="always_last",
        queue=False,
        show_progress="hidden",
    )
    example_select.input(
        fn=_example_preview_text,
        inputs=example_select,
        outputs=example_info,
        trigger_mode="always_last",
        show_progress="hidden",
    )
    load_example_btn.click(
        fn=load_demo_example,
        inputs=example_select,
        outputs=[image, example_info],
        concurrency_limit=1,
        trigger_mode="always_last",
        show_progress="minimal",
    ).success(
        fn=clear_outputs_with_quality,
        inputs=image,
        outputs=common_outputs,
        concurrency_limit=1,
        concurrency_id=RESULT_RESET_CONCURRENCY_ID,
        trigger_mode="always_last",
        show_progress="hidden",
    )
    batch_select.input(
        fn=select_batch_item,
        inputs=[batch_select, batch_state, show_summary],
        outputs=[
            original_output,
            model_input_output,
            result_output,
            comparison_section,
            comparison_view,
            result_image_file,
            result_image_path,
            download_result_btn,
            visible_class_filter,
            det_table,
            advice_box,
            quality_box,
            summary,
            chatbot,
            chat_state,
            export_file,
            export_path,
            word_report_file,
            word_report_path,
            export_word_btn,
            report_file,
            report_path,
            export_report_btn,
            save_case_btn,
            report_export_menu_btn,
            report_export_status,
            c.open_word_report_dir_btn,
            c.open_report_dir_btn,
        ],
        concurrency_limit=1,
        concurrency_id=RESULT_VIEW_CONCURRENCY_ID,
        trigger_mode="always_last",
        show_progress="minimal",
    )
    visible_class_filter.input(
        fn=update_detection_visibility,
        inputs=[visible_class_filter, batch_select, batch_state],
        outputs=[
            result_output,
            batch_state,
            det_table,
            result_image_file,
            result_image_path,
        ],
        concurrency_limit=1,
        concurrency_id=RESULT_VIEW_CONCURRENCY_ID,
        trigger_mode="always_last",
        show_progress="minimal",
    )
    ai_enabled.input(
        fn=toggle_ai_settings,
        inputs=ai_enabled,
        outputs=ai_group,
        queue=False,
        show_progress="hidden",
    )
    key_mode.input(
        fn=set_api_key_mode,
        inputs=[
            key_mode,
            direct_api_key_hidden,
            direct_api_key_visible,
            direct_key_visible,
        ],
        outputs=[env_api_key, direct_api_key_hidden, direct_api_key_visible, show_direct_key_btn, direct_key_visible],
        queue=False,
        show_progress="hidden",
    )
    show_direct_key_btn.click(
        fn=toggle_direct_key_visibility,
        inputs=[direct_api_key_hidden, direct_api_key_visible, direct_key_visible],
        outputs=[direct_api_key_hidden, direct_api_key_visible, show_direct_key_btn, direct_key_visible],
        queue=False,
        show_progress="hidden",
    )
    model_mode_event = model_mode.input(
        fn=sync_model_mode,
        inputs=[model_mode, primary_model_path, compare_model_path],
        outputs=[
            model_mode,
            settings_model_mode,
            compare_model_path,
            model_mode_feedback,
            settings_feedback,
        ],
        queue=False,
        show_progress="hidden",
    )
    chain_detection_result_reset(model_mode_event)
    settings_model_mode_event = settings_model_mode.input(
        fn=sync_model_mode,
        inputs=[settings_model_mode, primary_model_path, compare_model_path],
        outputs=[
            model_mode,
            settings_model_mode,
            compare_model_path,
            model_mode_feedback,
            settings_feedback,
        ],
        queue=False,
        show_progress="hidden",
    )
    chain_detection_result_reset(settings_model_mode_event)
    enable_compare_event = enable_compare.input(
        fn=on_enable_compare_change,
        inputs=enable_compare,
        outputs=[model_mode, settings_model_mode, compare_model_path],
        queue=False,
        show_progress="hidden",
    )
    chain_detection_result_reset(enable_compare_event)
    show_summary.input(
        fn=toggle_summary,
        inputs=show_summary,
        outputs=summary,
        queue=False,
        show_progress="hidden",
    )
    test_btn.click(
        fn=test_ai_settings,
        inputs=settings.ai_request_inputs(),
        outputs=test_result,
        concurrency_limit=1,
        concurrency_id=AI_REQUEST_CONCURRENCY_ID,
        trigger_mode="always_last",
        show_progress="minimal",
    )
    save_settings_btn.click(
        fn=save_ui_settings,
        inputs=[
            ai_enabled,
            base_url,
            ai_model,
            key_mode,
            env_api_key,
            direct_api_key_hidden,
            direct_api_key_visible,
            direct_key_visible,
            save_key,
            auto_save,
            storage_dir,
            custom_prompt,
            advice_style,
            enable_compare,
            show_summary,
            settings_model_mode,
            model_dir,
            primary_model_path,
            compare_model_path,
            save_history,
            history_limit,
            title_generation_mode,
            title_generation_prompt,
            followup_generation_enabled,
            followup_generation_prompt,
            task_model,
            task_temperature,
            task_max_tokens,
            keep_followup_prompts,
            followup_click_action,
            magnifier_enabled,
        ],
        outputs=[
            settings_feedback,
            case_select,
            case_table,
            case_detail,
            case_feedback,
            patient_feedback,
            new_patient_name,
            new_patient_reference,
            history_select,
            history_table,
            history_detail,
            history_feedback,
            case_report_file,
            case_report_path,
            patient_select,
            case_patient_select,
            history_patient_select,
            archived_patient_select,
            edit_patient_name,
            edit_patient_reference,
            archive_patient_btn,
            restore_patient_btn,
            case_loaded_state,
            history_loaded_state,
            storage_changed_state,
        ],
        concurrency_limit=1,
        concurrency_id=RECORD_WRITE_CONCURRENCY_ID,
        show_progress="minimal",
    ).success(
        fn=clear_session_after_storage_change,
        inputs=storage_changed_state,
        outputs=[image, batch_files, *common_outputs, case_id, case_note, chat_input],
        queue=False,
        show_progress="hidden",
    ).success(
        fn=refresh_report_center_after_storage_change,
        inputs=[storage_changed_state, storage_dir, history_patient_select],
        outputs=report_list_outputs,
        trigger_mode="always_last",
        show_progress="minimal",
    ).success(
        fn=refresh_conversations_after_storage_change,
        inputs=[
            storage_changed_state,
            conversation_loaded_state,
            storage_dir,
            patient_select,
        ],
        outputs=[
            conversation_select,
            conversation_feedback,
            conversation_loaded_state,
        ],
        trigger_mode="always_last",
        show_progress="minimal",
    ).success(
        fn=refresh_ai_runtime_status,
        inputs=[
            chat_state,
            batch_state,
            batch_select,
            *settings.ai_request_inputs(),
        ],
        outputs=ai_runtime_status,
        queue=False,
        show_progress="hidden",
    )
