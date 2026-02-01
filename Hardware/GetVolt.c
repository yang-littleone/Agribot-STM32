#include "GetVolt.h"
#include "adc.h"

/*
 * @brief 获取ADC值
 * @param 无
 * @retval ADC值，范围0~4095
 */
uint16_t GetADValue(void)
{
    uint16_t adc_val = 0;
    HAL_ADC_Start(&hadc1);
    HAL_ADC_PollForConversion(&hadc1, 5);
    if (HAL_IS_BIT_SET(HAL_ADC_GetState(&hadc1), HAL_ADC_STATE_REG_EOC))
    {
        adc_val = HAL_ADC_GetValue(&hadc1);
    }
    return adc_val;
}

/*
 * @brief 获取电压值
 * @param 无
 * @retval 电压值，单位：V
 */
float GetVoltValue(void)
{
    float volt_val = 0.0f;
    uint16_t adc_val = GetADValue();
    volt_val = (float)adc_val * 3.3f / 4095.0f * 11;
    return volt_val;
}