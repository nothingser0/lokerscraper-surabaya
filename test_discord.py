#!/usr/bin/env python3
"""Test script to send a dummy job notification to all configured Discord webhooks."""

from notifiers import notify_new_jobs

dummy_job = {
    'title': 'Test Backend Developer',
    'company': 'Test Company PT',
    'location': 'Surabaya',
    'url': 'https://example.com/job/test-12345',
    'source': 'JobStreet',
    'salary_min': 'Rp 8.000.000',
    'salary_max': 'Rp 12.000.000',
    'work_type': 'Full-time',
    'work_mode': 'Hybrid',
    'posted_at': '2026-09-04',
    'experience': '2-3 years',
    'skills': ['Python', 'Django', 'PostgreSQL', 'Docker'],
    'benefits': ['Health Insurance', 'Flexible Hours', 'Remote Work'],
    'job_description': 'This is a test notification to verify that Discord webhooks are working correctly. If you see this message, the notification system is functioning properly.'
}

print("Sending test notification to all configured Discord webhooks...")
notify_new_jobs([dummy_job])
print("✅ Test notification sent! Check your Discord channels.")
