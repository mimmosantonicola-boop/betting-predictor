@echo off
:: Copies our custom files into the MiroFish directory

if not exist "mirofish" (
    echo [ERROR] mirofish directory not found.
    exit /b 1
)

:: Backend config (removes Zep requirement, adds local memory path)
copy /Y "patches\backend\app\config.py" "mirofish\backend\app\config.py"

:: Local Zep replacement
copy /Y "patches\backend\app\services\local_zep.py" "mirofish\backend\app\services\local_zep.py"

:: Patched Zep service files
copy /Y "patches\backend\app\services\zep_entity_reader.py" "mirofish\backend\app\services\zep_entity_reader.py"
copy /Y "patches\backend\app\services\zep_graph_memory_updater.py" "mirofish\backend\app\services\zep_graph_memory_updater.py"
copy /Y "patches\backend\app\services\zep_tools.py" "mirofish\backend\app\services\zep_tools.py"

:: Modified requirements (removes zep-cloud, adds our deps)
copy /Y "patches\backend\requirements.txt" "mirofish\backend\requirements.txt"

:: Betting dashboard Vue component
copy /Y "patches\frontend\src\views\BettingView.vue" "mirofish\frontend\src\views\BettingView.vue"

:: Router patch — inject Betting route
python patches\inject_router.py

echo [OK] All patches applied.
