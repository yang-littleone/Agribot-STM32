#ifndef BATTERY_ADC_STUB
#define BATTERY_ADC_STUB
#include <stdint.h>
typedef enum {HAL_OK=0,HAL_ERROR=1,HAL_BUSY=2,HAL_TIMEOUT=3} HAL_StatusTypeDef;
typedef struct {unsigned unused;} ADC_HandleTypeDef;
extern ADC_HandleTypeDef hadc1;
HAL_StatusTypeDef HAL_ADC_Start(ADC_HandleTypeDef *h);
HAL_StatusTypeDef HAL_ADC_Stop(ADC_HandleTypeDef *h);
HAL_StatusTypeDef HAL_ADC_PollForConversion(ADC_HandleTypeDef *h,uint32_t timeout);
uint32_t HAL_ADC_GetValue(ADC_HandleTypeDef *h);
#endif
