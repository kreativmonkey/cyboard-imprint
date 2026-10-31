zephyr_library()
zephyr_library_sources(src/behavior_battery_led.c)

# ZMK does not expose a temporary RGB overlay API. Apply the small, pinned
# extension before its sources are compiled, on both local and GitHub builds.
set(zmk_source_root "${APPLICATION_SOURCE_DIR}/..")
set(battery_patch "${CMAKE_CURRENT_LIST_DIR}/../patches/zmk-battery-led.patch")
execute_process(
  COMMAND git apply --reverse --check "${battery_patch}"
  WORKING_DIRECTORY "${zmk_source_root}"
  RESULT_VARIABLE patch_already_applied
  OUTPUT_QUIET ERROR_QUIET
)
if(NOT patch_already_applied EQUAL 0)
  execute_process(
    COMMAND git apply --check "${battery_patch}"
    WORKING_DIRECTORY "${zmk_source_root}"
    RESULT_VARIABLE patch_check_result
  )
  if(NOT patch_check_result EQUAL 0)
    message(FATAL_ERROR "Battery LED patch does not fit the pinned ZMK revision")
  endif()
  execute_process(
    COMMAND git apply "${battery_patch}"
    WORKING_DIRECTORY "${zmk_source_root}"
    COMMAND_ERROR_IS_FATAL ANY
  )
endif()
