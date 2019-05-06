/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#include <stdio.h>
#include <Python.h>

int main() {
  printf("Hello, world! (from C)\n");

  // Initialize the Python VM
  Py_Initialize();

  PyRun_SimpleString("print(\'Hello, world! (from Python from C)\')");

  if (Py_FinalizeEx() < 0) {
    fprintf(stderr, "failed to finalize Python VM\n");
    return 1;
  }
}
