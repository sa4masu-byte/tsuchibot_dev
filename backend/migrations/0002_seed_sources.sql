-- Public, non-secret source definitions supplied by the project owner.

insert into config.source_definitions
    (source_code, location_id, display_name, priority, public_config)
values
    (
        'jimoty',
        'profile-67cea788596d2b1549267ce8',
        'Jimoty Spot Hiratsuka',
        1,
        '{"articles_url":"https://jmty.jp/profiles/67cea788596d2b1549267ce8/articles"}'::jsonb
    ),
    (
        'jimoty',
        'profile-68e5fa043b084d63ba34bea6',
        'Jimoty Spot Fujisawa Tsujido',
        2,
        '{"articles_url":"https://jmty.jp/profiles/68e5fa043b084d63ba34bea6/articles"}'::jsonb
    ),
    ('amazon', null, 'Amazon', 3, '{}'::jsonb),
    ('rakuten', null, 'Rakuten', 4, '{}'::jsonb),
    ('aliexpress', null, 'AliExpress', 5, '{}'::jsonb),
    ('shein', null, 'SHEIN', 6, '{}'::jsonb)
on conflict (source_code, location_id) do nothing;
