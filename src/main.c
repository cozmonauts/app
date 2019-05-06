/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#include <stdio.h>

#include "service/python.h"
#include "global.h"
#include "service.h"

int main(int argc, char* argv[]) {
  g_mut->argc = argc;
  g_mut->argv = (const char**) argv;

  service_load(SERVICE_PYTHON);
  service_start(SERVICE_PYTHON);

  // TODO

  service_stop(SERVICE_PYTHON);
  service_unload(SERVICE_PYTHON);
}
