exocortex/                   <- Весь репозиторий
  README.md
  .gitignore
  .env.example
  requirements.txt
  pyproject.toml (опционально)
  
  docs/                      <- Документация, спецификации, планы
    context_exocortex.md
    freeminder_spec.md
    roadmap.md
    decisions.md

  data/                      <- Данные пользователя, профили, примеры
    user_profile.json

  scripts/                   <- Вспомогательные скрипты, миграции, утилиты
    migrate.py
    export_tg_json_loader.py (если понадобится)

  tests/                     <- unit-тесты и integration-тесты
    test_core.py
    test_freeminder.py
    test_telegram.py
    ...

  src/
    exocortex/               <- Сам Python-пакет
      __init__.py

      core/                  <- Ядро всей системы
        __init__.py
        config.py
        db.py
        models.py
        openai_client.py

      memory/                <- Second Brain
        __init__.py
        base_memory.py
        knowledge.py
        graph.py (позже)

      integrations/
        __init__.py
        telegram_client.py
        google_calendar.py
        google_drive.py

      modules/               <- Модули/приложения
        __init__.py

        freeminder/
          __init__.py
          pipeline.py
          prompts.py
          rules.py

        # future
        # second_brain/
        #   cleanup.py
        #   entity_extraction.py
        # composer0/
        #   orchestrator.py
        #   agent_registry.py

      cli/                    <- Командные утилиты
        __init__.py
        import_telegram.py
        import_calendar.py
        run_freeminder.py
        query_cli.py