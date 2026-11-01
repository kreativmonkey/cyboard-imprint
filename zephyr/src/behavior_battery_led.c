#define DT_DRV_COMPAT zmk_behavior_battery_led

#include <zephyr/device.h>
#include <drivers/behavior.h>
#include <zmk/battery.h>
#include <zmk/behavior.h>
#include <zmk/rgb_underglow.h>

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)

static int on_keymap_binding_pressed(struct zmk_behavior_binding *binding,
                                     struct zmk_behavior_binding_event event) {
    return zmk_rgb_underglow_show_battery(zmk_battery_state_of_charge());
}

static const struct behavior_driver_api battery_led_driver_api = {
    .binding_pressed = on_keymap_binding_pressed,
    .locality = BEHAVIOR_LOCALITY_GLOBAL,
#if IS_ENABLED(CONFIG_ZMK_BEHAVIOR_METADATA)
    .get_parameter_metadata = zmk_behavior_get_empty_param_metadata,
#endif
};

#define BATTERY_LED_INST(n)                                                                         \
    BEHAVIOR_DT_INST_DEFINE(n, NULL, NULL, NULL, NULL, POST_KERNEL,                                 \
                            CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &battery_led_driver_api);

DT_INST_FOREACH_STATUS_OKAY(BATTERY_LED_INST)

#endif
