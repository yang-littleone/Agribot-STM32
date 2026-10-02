#ifndef WRS_EXPERIMENT_H
#define WRS_EXPERIMENT_H
#include "CarControl.h"
void WRS_Init(void);
void WRS_RecordEncoder(const Encoder_t *counts);
void WRS_ControlTask(void *arg);
void WRS_UartTask(void *arg);
void WRS_EmergencyZero(void);
#endif
