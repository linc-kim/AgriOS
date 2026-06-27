-- AGRIOS — Role Seed Data
-- Applied by Alembic Migration 001 via bulk_insert.
-- This file is a human-readable reference only.
-- Do NOT run this file directly — use Alembic migrations.

-- 8 roles as defined in Engineering Constitution Section 5

INSERT INTO roles (id, name, display_name, description, is_platform_role, created_at, updated_at, metadata)
VALUES
  (gen_random_uuid(), 'super_admin',       'Super Admin',       'Full platform access. Founder only.', TRUE,  NOW(), NOW(), '{}'),
  (gen_random_uuid(), 'platform_admin',    'Platform Admin',    'Platform management. Future AGRIOS staff.', TRUE,  NOW(), NOW(), '{}'),
  (gen_random_uuid(), 'enterprise_owner',  'Enterprise Owner',  'Multi-farm account. Deferred to V2.', FALSE, NOW(), NOW(), '{}'),
  (gen_random_uuid(), 'farm_owner',        'Farm Owner',        'Full access to one farm. Default role.', FALSE, NOW(), NOW(), '{}'),
  (gen_random_uuid(), 'farm_manager',      'Farm Manager',      'All operations. Cannot delete farm.', FALSE, NOW(), NOW(), '{}'),
  (gen_random_uuid(), 'vet_consultant',    'Vet / Consultant',  'Read-only health data access.', FALSE, NOW(), NOW(), '{}'),
  (gen_random_uuid(), 'farm_worker',       'Farm Worker',       'Daily operations only.', FALSE, NOW(), NOW(), '{}'),
  (gen_random_uuid(), 'viewer',            'Viewer',            'Read-only access.', FALSE, NOW(), NOW(), '{}')
ON CONFLICT (name) DO NOTHING;
