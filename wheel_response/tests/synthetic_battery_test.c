#include "WheelResponseBattery.h"
#include "adc.h"
#include <assert.h>
#include <stdio.h>
ADC_HandleTypeDef hadc1;
static uint32_t value=1360;
static HAL_StatusTypeDef start_status=HAL_OK,poll_status=HAL_OK;
static unsigned starts,stops;
HAL_StatusTypeDef HAL_ADC_Start(ADC_HandleTypeDef *h){(void)h;starts++;return start_status;}
HAL_StatusTypeDef HAL_ADC_Stop(ADC_HandleTypeDef *h){(void)h;stops++;return HAL_OK;}
HAL_StatusTypeDef HAL_ADC_PollForConversion(ADC_HandleTypeDef *h,uint32_t timeout){(void)h;assert(timeout==0);return poll_status;}
uint32_t HAL_ADC_GetValue(ADC_HandleTypeDef *h){(void)h;return value;}
int main(void){
    assert(WRS_BatteryMv(0)==65535);WRS_BatteryPoll(0);assert(starts==1);
    WRS_BatteryPoll(1);assert(WRS_BatteryRaw()==1360&&WRS_BatteryMv(1)==12056);
    WRS_BatteryPoll(99);assert(starts==1);assert(WRS_BatteryMv(502)==65535);
    value=4095;WRS_BatteryPoll(600);WRS_BatteryPoll(601);assert(WRS_BatteryMv(601)==65535);
    poll_status=HAL_TIMEOUT;WRS_BatteryPoll(700);WRS_BatteryPoll(719);assert(stops==2);
    WRS_BatteryPoll(720);assert(stops==3&&WRS_BatteryRaw()==65535);
    start_status=HAL_ERROR;WRS_BatteryPoll(800);assert(WRS_BatteryMv(800)==65535);
    start_status=HAL_OK;poll_status=HAL_OK;value=2048;WRS_BatteryPoll(900);WRS_BatteryPoll(901);
    assert(WRS_BatteryMv(901)==18154);
    WRS_BatteryPoll(0xfffffffeu);WRS_BatteryPoll(0xffffffffu);
    assert(WRS_BatteryMv(5)==18154&&WRS_BatteryMv(500)==65535);
    puts("Synthetic nonblocking ADC estimate, stale/failure/clipping and wrap checks passed.");return 0;
}
