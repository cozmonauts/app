/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#ifndef SERVICE_PYTHON_H
#define SERVICE_PYTHON_H

/** Client operations. */
enum service_python_op {
  /** Friends list mode. */
  service_python_op_friends_list,

  /** Friends remove mode. */
  service_python_op_friends_remove,

  /** Interactive mode. */
  service_python_op_interact,
};

/** Python service functions. */
enum service_python_fn {
  /** Execute a client operation. */
  service_python_fn_op_exec,
};

/** The Python service. */
extern struct service* const SERVICE_PYTHON;

#endif // #ifndef SERVICE_PYTHON_H
