/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#ifndef SERVICE_CONSOLE_H
#define SERVICE_CONSOLE_H

/** Console service functions. */
enum service_console_fn {
  /** Get and clear the interrupt status. */
  service_console_fn_interrupted,

  /** Execute a solicited prompt. */
  service_console_fn_solicit,
};

/** The console service. */
extern struct service* const SERVICE_CONSOLE;

#endif // #ifndef SERVICE_CONSOLE_H
