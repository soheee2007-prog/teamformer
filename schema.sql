-- 생성: 2026-10-29 23:25 KST
-- 팀 편성 앱의 테이블. 이름은 모두 tf_ 로 시작한다(공고 4.2절, 5장).

create table if not exists tf_students (
    id serial primary key,
    student_no text not null unique,
    name text not null,
    main_role text not null check (main_role in
        ('기획자', '웹 프로그래머', '프론트엔드 디자이너', '테스터', '보고서 작성자', '발표자', '관리자')),
    password_hash text not null,
    is_admin boolean not null default false
);

create table if not exists tf_student_sub_roles (
    student_id int not null references tf_students(id) on delete cascade,
    role text not null check (role in
        ('기획자', '웹 프로그래머', '프론트엔드 디자이너', '테스터', '보고서 작성자', '발표자')),
    primary key (student_id, role)
);

create table if not exists tf_teams (
    id serial primary key,
    team_no int not null unique,
    name text not null unique
);

-- (team_id, slot_no) 기본 키와 student_id 유일성이 "마지막 자리에 두 명이 동시에 들어감"과
-- "한 학생은 한 팀에만"을 DB에서 막는다.
create table if not exists tf_members (
    team_id int not null references tf_teams(id) on delete cascade,
    slot_no int not null check (slot_no between 1 and 4),
    student_id int not null unique references tf_students(id) on delete cascade,
    primary key (team_id, slot_no)
);

create table if not exists tf_applications (
    id serial primary key,
    team_id int not null references tf_teams(id) on delete cascade,
    student_id int not null references tf_students(id) on delete cascade,
    status text not null check (status in ('대기', '승인', '거절')),
    reason text,
    created_at timestamptz not null default now(),
    decided_at timestamptz
);

-- 한 학생은 결과를 기다리는 지원을 하나만 가질 수 있다.
create unique index if not exists tf_applications_one_pending
    on tf_applications(student_id) where status = '대기';

create table if not exists tf_votes (
    application_id int not null references tf_applications(id) on delete cascade,
    voter_id int not null references tf_students(id) on delete cascade,
    vote text not null check (vote in ('찬성', '거부')),
    primary key (application_id, voter_id)
);

create table if not exists tf_settings (
    key text primary key,
    value text not null
);

-- AI 호출 기록(README 5항의 근거).
create table if not exists tf_ai_logs (
    id serial primary key,
    created_at timestamptz not null default now(),
    model text not null,
    outcome text not null,
    detail text,
    seconds real
);
