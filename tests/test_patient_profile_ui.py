from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

import gradio as gr

import app
from src.dental_detection.personal_workspace import (
    PERSONAL_PATIENT_ID,
    create_personal_patient,
    get_personal_patient,
    personal_archived_patient_choices,
    personal_patient_choices,
)


class PatientProfileUiTests(unittest.TestCase):
    def test_update_archive_and_restore_callbacks_keep_selectors_aligned(self) -> None:
        with TemporaryDirectory() as temp_dir:
            patient = create_personal_patient(temp_dir, "家人", external_reference="P-1")
            updated = app.update_patient_profile(patient.id, "家庭成员", "P-2", temp_dir)

            self.assertEqual(len(updated), 7)
            self.assertTrue(all(item.get("value") == patient.id for item in updated[:3]))
            self.assertEqual(get_personal_patient(temp_dir, patient.id).display_name, "家庭成员")

            archived = app.archive_patient_profile(patient.id, temp_dir)
            self.assertEqual(len(archived), 9)
            self.assertTrue(all(item.get("value") == PERSONAL_PATIENT_ID for item in archived[:3]))
            self.assertNotIn(patient.id, {value for _, value in personal_patient_choices(temp_dir)})
            self.assertIn(patient.id, {value for _, value in personal_archived_patient_choices(temp_dir)})

            restored = app.restore_patient_profile(patient.id, temp_dir)
            self.assertEqual(len(restored), 9)
            self.assertTrue(all(item.get("value") == patient.id for item in restored[:3]))
            self.assertIn(patient.id, {value for _, value in personal_patient_choices(temp_dir)})

    def test_default_personal_profile_cannot_be_archived(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app.ensure_personal_workspace(temp_dir)
            _, _, archive_button = app.load_patient_profile_form(PERSONAL_PATIENT_ID, temp_dir)

            self.assertFalse(archive_button.get("interactive"))
            with self.assertRaises(gr.Error):
                app.archive_patient_profile(PERSONAL_PATIENT_ID, temp_dir)


if __name__ == "__main__":
    unittest.main()
