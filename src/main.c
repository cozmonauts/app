/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#include <stdio.h>
#include <stdlib.h>

#include <linenoise.h>

#include "global.h"

int main(int argc, char* argv[]) {
  g_mut->argc = argc;
  g_mut->argv = (const char**) argv;

  char* line;
  while ((line = linenoise("C:\\> ")) != NULL) {
    if (line[0] != '\0') {
      printf("echo: %s\n", line);
    }
    free(line);
  }
}
