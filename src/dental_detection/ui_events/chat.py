from __future__ import annotations

from types import ModuleType, SimpleNamespace


def bind_chat_events(c: SimpleNamespace, h: ModuleType) -> None:
    """Bind the AI conversation lifecycle and cancellation rules."""
    AI_REQUEST_CONCURRENCY_ID = h.AI_REQUEST_CONCURRENCY_ID
    branch_chat_conversation = h.branch_chat_conversation
    chat_export_button_state = h.chat_export_button_state
    clear_ai_workspace_with_status = h.clear_ai_workspace_with_status
    continue_chat_in_workspace = h.continue_chat_in_workspace
    delete_ai_workspace_conversation = h.delete_ai_workspace_conversation
    edit_chat_message = h.edit_chat_message
    gr = h.gr
    load_ai_workspace_conversation = h.load_ai_workspace_conversation
    refresh_ai_runtime_status = h.refresh_ai_runtime_status
    refresh_conversation_history = h.refresh_conversation_history
    regenerate_last_chat_response = h.regenerate_last_chat_response
    rename_conversation_history_item = h.rename_conversation_history_item
    retry_chat_response = h.retry_chat_response
    run_chat_automation = h.run_chat_automation
    search_conversation_history = h.search_conversation_history
    add_patient_btn = c.add_patient_btn
    advice_style = c.advice_style
    ai_enabled = c.ai_enabled
    ai_model = c.ai_model
    ai_runtime_status = c.ai_runtime_status
    archive_patient_btn = c.archive_patient_btn
    auto_save = c.auto_save
    base_url = c.base_url
    batch_files = c.batch_files
    batch_select = c.batch_select
    batch_state = c.batch_state
    branch_conversation_btn = c.branch_conversation_btn
    branch_index_input = c.branch_index_input
    case_patient_select = c.case_patient_select
    chat_btn = c.chat_btn
    chat_input = c.chat_input
    chat_state = c.chat_state
    chat_suggestion_buttons = c.chat_suggestion_buttons
    chatbot = c.chatbot
    clear_chat_btn = c.clear_chat_btn
    clear_session_btn = c.clear_session_btn
    conversation_feedback = c.conversation_feedback
    conversation_search = c.conversation_search
    conversation_select = c.conversation_select
    conversation_title_input = c.conversation_title_input
    current_conversation_file_state = c.current_conversation_file_state
    custom_prompt = c.custom_prompt
    delete_conversation_btn = c.delete_conversation_btn
    direct_api_key_hidden = c.direct_api_key_hidden
    direct_api_key_visible = c.direct_api_key_visible
    env_api_key = c.env_api_key
    export_btn = c.export_btn
    export_file = c.export_file
    export_path = c.export_path
    history_patient_select = c.history_patient_select
    image = c.image
    key_mode = c.key_mode
    load_conversation_btn = c.load_conversation_btn
    patient_select = c.patient_select
    refresh_conversation_btn = c.refresh_conversation_btn
    regenerate_chat_btn = c.regenerate_chat_btn
    rename_conversation_btn = c.rename_conversation_btn
    restore_patient_btn = c.restore_patient_btn
    save_settings_btn = c.save_settings_btn
    settings = c.settings
    stop_chat_btn = c.stop_chat_btn
    storage_dir = c.storage_dir

    chat_event = gr.on(
        triggers=[chat_btn.click, chat_input.submit],
        fn=continue_chat_in_workspace,
        inputs=[
            chat_input,
            chat_state,
            current_conversation_file_state,
            *settings.ai_request_inputs(),
            patient_select,
            batch_state,
            batch_select,
        ],
        outputs=[
            chatbot,
            chat_state,
            chat_input,
            export_file,
            export_path,
            current_conversation_file_state,
            conversation_title_input,
        ],
        concurrency_limit=1,
        concurrency_id=AI_REQUEST_CONCURRENCY_ID,
        trigger_mode="once",
        show_progress="minimal",
    )
    regenerate_event = regenerate_chat_btn.click(
        fn=regenerate_last_chat_response,
        inputs=[
            chat_state,
            current_conversation_file_state,
            *settings.ai_request_inputs(),
            patient_select,
            batch_state,
            batch_select,
        ],
        outputs=[
            chatbot,
            chat_state,
            chat_input,
            export_file,
            export_path,
            current_conversation_file_state,
            conversation_title_input,
        ],
        concurrency_limit=1,
        concurrency_id=AI_REQUEST_CONCURRENCY_ID,
        trigger_mode="once",
        show_progress="minimal",
    )
    retry_event = chatbot.retry(
        fn=retry_chat_response,
        inputs=[
            chat_state,
            current_conversation_file_state,
            *settings.ai_request_inputs(),
            patient_select,
            batch_state,
            batch_select,
        ],
        outputs=[
            chatbot,
            chat_state,
            chat_input,
            export_file,
            export_path,
            current_conversation_file_state,
            conversation_title_input,
        ],
        concurrency_limit=1,
        concurrency_id=AI_REQUEST_CONCURRENCY_ID,
        trigger_mode="once",
        show_progress="minimal",
    )
    edit_event = chatbot.edit(
        fn=edit_chat_message,
        inputs=[
            chat_state,
            current_conversation_file_state,
            *settings.ai_request_inputs(),
            patient_select,
            batch_state,
            batch_select,
        ],
        outputs=[
            chatbot,
            chat_state,
            chat_input,
            export_file,
            export_path,
            current_conversation_file_state,
            conversation_title_input,
        ],
        concurrency_limit=1,
        concurrency_id=AI_REQUEST_CONCURRENCY_ID,
        trigger_mode="once",
        show_progress="minimal",
    )
    stop_chat_btn.click(
        fn=None,
        cancels=[chat_event, regenerate_event, retry_event, edit_event],
        queue=False,
        show_progress="hidden",
    )
    chat_event.success(
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
    chat_event.success(
        fn=run_chat_automation,
        inputs=[
            chat_state,
            current_conversation_file_state,
            conversation_title_input,
            auto_save,
            storage_dir,
            patient_select,
        ],
        outputs=[
            conversation_select,
            conversation_feedback,
            conversation_title_input,
            *chat_suggestion_buttons,
            chatbot,
            chat_state,
        ],
        concurrency_limit=1,
        concurrency_id=AI_REQUEST_CONCURRENCY_ID,
        show_progress="hidden",
    )
    regenerate_event.success(
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
    for revision_event in (retry_event, edit_event):
        revision_event.success(
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
        revision_event.success(
            fn=run_chat_automation,
            inputs=[
                chat_state,
                current_conversation_file_state,
                conversation_title_input,
                auto_save,
                storage_dir,
                patient_select,
            ],
            outputs=[
                conversation_select,
                conversation_feedback,
                conversation_title_input,
                *chat_suggestion_buttons,
                chatbot,
                chat_state,
            ],
            concurrency_limit=1,
            concurrency_id=AI_REQUEST_CONCURRENCY_ID,
            show_progress="hidden",
        )
    regenerate_event.success(
        fn=run_chat_automation,
        inputs=[
            chat_state,
            current_conversation_file_state,
            conversation_title_input,
            auto_save,
            storage_dir,
            patient_select,
        ],
        outputs=[
            conversation_select,
            conversation_feedback,
            conversation_title_input,
            *chat_suggestion_buttons,
            chatbot,
            chat_state,
        ],
        concurrency_limit=1,
        concurrency_id=AI_REQUEST_CONCURRENCY_ID,
        show_progress="hidden",
    )
    chatbot.change(
        fn=chat_export_button_state,
        inputs=chatbot,
        outputs=export_btn,
        queue=False,
        show_progress="hidden",
    )
    gr.on(
        triggers=[
            patient_select.input,
            case_patient_select.input,
            history_patient_select.input,
            add_patient_btn.click,
            archive_patient_btn.click,
            restore_patient_btn.click,
            clear_session_btn.click,
            save_settings_btn.click,
            ai_enabled.input,
            base_url.input,
            ai_model.input,
            key_mode.input,
            env_api_key.input,
            direct_api_key_hidden.input,
            direct_api_key_visible.input,
            auto_save.input,
            storage_dir.input,
            custom_prompt.input,
            advice_style.input,
            load_conversation_btn.click,
        ],
        fn=None,
        cancels=[chat_event, regenerate_event, retry_event, edit_event],
        queue=False,
        show_progress="hidden",
    )
    clear_chat_btn.click(
        fn=clear_ai_workspace_with_status,
        inputs=[batch_state, batch_select, *settings.ai_request_inputs()],
        outputs=[
            chatbot,
            chat_state,
            chat_input,
            export_file,
            export_path,
            ai_runtime_status,
            current_conversation_file_state,
            conversation_title_input,
            *chat_suggestion_buttons,
            conversation_feedback,
        ],
        cancels=[chat_event, regenerate_event, retry_event, edit_event],
        queue=False,
        show_progress="hidden",
    )
    chatbot.clear(
        fn=clear_ai_workspace_with_status,
        inputs=[batch_state, batch_select, *settings.ai_request_inputs()],
        outputs=[
            chatbot,
            chat_state,
            chat_input,
            export_file,
            export_path,
            ai_runtime_status,
            current_conversation_file_state,
            conversation_title_input,
            *chat_suggestion_buttons,
            conversation_feedback,
        ],
        cancels=[chat_event, regenerate_event, retry_event, edit_event],
        queue=False,
        show_progress="hidden",
    )
    refresh_conversation_btn.click(
        fn=refresh_conversation_history,
        inputs=[storage_dir, patient_select],
        outputs=[conversation_select, conversation_feedback],
        trigger_mode="always_last",
        show_progress="minimal",
    )
    gr.on(
        triggers=[conversation_search.input, conversation_search.submit],
        fn=search_conversation_history,
        inputs=[conversation_search, storage_dir, patient_select],
        outputs=[conversation_select, conversation_feedback],
        trigger_mode="always_last",
        queue=False,
        show_progress="hidden",
    )
    load_conversation_btn.click(
        fn=load_ai_workspace_conversation,
        inputs=[
            conversation_select,
            storage_dir,
            patient_select,
            batch_state,
            batch_select,
            *settings.ai_request_inputs(),
        ],
        outputs=[
            chatbot,
            chat_state,
            chat_input,
            export_file,
            export_path,
            conversation_feedback,
            ai_runtime_status,
            current_conversation_file_state,
            conversation_title_input,
            *chat_suggestion_buttons,
        ],
        trigger_mode="always_last",
        show_progress="minimal",
    )
    conversation_select.input(
        fn=load_ai_workspace_conversation,
        inputs=[
            conversation_select,
            storage_dir,
            patient_select,
            batch_state,
            batch_select,
            *settings.ai_request_inputs(),
        ],
        outputs=[
            chatbot,
            chat_state,
            chat_input,
            export_file,
            export_path,
            conversation_feedback,
            ai_runtime_status,
            current_conversation_file_state,
            conversation_title_input,
            *chat_suggestion_buttons,
        ],
        trigger_mode="always_last",
        show_progress="minimal",
    )
    rename_conversation_btn.click(
        fn=rename_conversation_history_item,
        inputs=[
            conversation_select,
            conversation_title_input,
            storage_dir,
            patient_select,
            conversation_search,
        ],
        outputs=[
            conversation_select,
            conversation_title_input,
            conversation_feedback,
        ],
        trigger_mode="always_last",
        show_progress="minimal",
    )
    delete_conversation_event = delete_conversation_btn.click(
        fn=delete_ai_workspace_conversation,
        inputs=[
            conversation_select,
            current_conversation_file_state,
            storage_dir,
            patient_select,
            conversation_search,
        ],
        outputs=[
            conversation_select,
            conversation_title_input,
            conversation_feedback,
            chatbot,
            chat_state,
            current_conversation_file_state,
        ],
        cancels=[chat_event, regenerate_event, retry_event, edit_event],
        trigger_mode="always_last",
        show_progress="minimal",
    )
    delete_conversation_event.success(
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
    branch_conversation_event = branch_conversation_btn.click(
        fn=branch_chat_conversation,
        inputs=[
            branch_index_input,
            chat_state,
            storage_dir,
            patient_select,
            conversation_search,
        ],
        outputs=[
            chatbot,
            chat_state,
            current_conversation_file_state,
            conversation_title_input,
            conversation_select,
            conversation_feedback,
        ],
        cancels=[chat_event, regenerate_event, retry_event, edit_event],
        trigger_mode="always_last",
        show_progress="minimal",
    )
    branch_conversation_event.success(
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
    gr.on(
        triggers=[
            image.input,
            batch_files.upload,
            batch_select.input,
            patient_select.input,
            case_patient_select.input,
            history_patient_select.input,
            clear_session_btn.click,
        ],
        fn=lambda: ("", ""),
        outputs=[current_conversation_file_state, conversation_title_input],
        queue=False,
        show_progress="hidden",
    )
