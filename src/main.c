/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#define LOG_TAG "main"

#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "service/python.h"
#include "global.h"
#include "service.h"
#include "log.h"

static volatile int interrupted;

static void sigint(int nada) {
  printf("Interrupted\n");
  interrupted = 1;
}

int main(int argc, char* argv[]) {
  g_mut->argc = argc;
  g_mut->argv = (const char**) argv;

  // Load services
  service_load(SERVICE_PYTHON);

  // Start services
  service_start(SERVICE_PYTHON);

  // Call interact operation
  service_call(SERVICE_PYTHON, service_python_fn_op_exec, (const void*) service_python_op_interact, NULL);

  // Enable automatic mode
  service_call(SERVICE_PYTHON, service_python_fn_interact_auto_enable, NULL, NULL);

  sleep(10);

  // Disable automatic mode
  service_call(SERVICE_PYTHON, service_python_fn_interact_auto_disable, NULL, NULL);

  sleep(5);

  // Request to start watching faces
  service_call(SERVICE_PYTHON, service_python_fn_interact_manual_req_diversion_faces, NULL, NULL);

  sleep(10);

  // Enable automatic mode
  service_call(SERVICE_PYTHON, service_python_fn_interact_manual_return, NULL, NULL);
  service_call(SERVICE_PYTHON, service_python_fn_interact_auto_enable, NULL, NULL);

  sleep(40);

  service_call(SERVICE_PYTHON, service_python_fn_interact_test_low_battery, NULL, NULL);

  // Wait for ^C
  signal(SIGINT, &sigint);
  while (!interrupted);

  // Stop services
  service_stop(SERVICE_PYTHON);

  // Unload services
  service_unload(SERVICE_PYTHON);
}
