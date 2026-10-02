#include "WheelResponseBattery.h"
#include "adc.h"
static volatile uint16_t cached_mv=WRS_BATTERY_INVALID,raw_count=WRS_BATTERY_INVALID;
static volatile uint32_t last_success_ms;
static uint32_t last_attempt_ms,conversion_start_ms;
static uint8_t pending,attempted;
uint16_t WRS_BatteryMv(uint32_t now_ms){
    uint16_t value=cached_mv;
    return value!=WRS_BATTERY_INVALID&&(uint32_t)(now_ms-last_success_ms)<=500u?value:WRS_BATTERY_INVALID;
}
uint16_t WRS_BatteryRaw(void){return raw_count;}
void WRS_BatteryPoll(uint32_t now_ms){
    HAL_StatusTypeDef status;
    if(pending){
        /* Zero timeout: no ADC wait in the motor control task or UART task. */
        status=HAL_ADC_PollForConversion(&hadc1,0);
        if(status==HAL_OK){
            uint32_t count=HAL_ADC_GetValue(&hadc1);
            HAL_ADC_Stop(&hadc1);pending=0;
            raw_count=count<=4095u?(uint16_t)count:WRS_BATTERY_INVALID;
            /* A full-scale ADC reading is clipped, not a valid battery voltage. */
            cached_mv=count<4095u?(uint16_t)((count*36300u+2047u)/4095u):WRS_BATTERY_INVALID;
            last_success_ms=now_ms;
        }else if(status!=HAL_TIMEOUT||(uint32_t)(now_ms-conversion_start_ms)>=20u){
            HAL_ADC_Stop(&hadc1);pending=0;cached_mv=raw_count=WRS_BATTERY_INVALID;
        }
        return;
    }
    if(!attempted||(uint32_t)(now_ms-last_attempt_ms)>=100u){
        attempted=1;last_attempt_ms=now_ms;
        if(HAL_ADC_Start(&hadc1)==HAL_OK){pending=1;conversion_start_ms=now_ms;}
        else cached_mv=raw_count=WRS_BATTERY_INVALID;
    }
}
