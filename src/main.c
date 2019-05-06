/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#include <stdio.h>
#include <unistd.h>

#include "service/python.h"
#include "global.h"
#include "service.h"

int main(int argc, char* argv[]) {
  g_mut->argc = argc;
  g_mut->argv = (const char**) argv;

  // Spin up Python service
  service_load(SERVICE_PYTHON);
  service_start(SERVICE_PYTHON);

  // Call interact operation
  service_call(SERVICE_PYTHON, service_python_fn_op_exec, (const void*) service_python_op_interact, NULL);

  sleep(25);

  // Shut down Python service
  service_stop(SERVICE_PYTHON);
  service_unload(SERVICE_PYTHON);
}
