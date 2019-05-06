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

  /** Enable automatic interaction. */
  service_python_fn_interact_auto_enable,

  /** Disable automatic interaction. */
  service_python_fn_interact_auto_disable,

  /** Test low battery condition. Works in manual and automatic modes. */
  service_python_fn_interact_test_low_battery,

  /** Manual mode. Advance the active Cozmo from the charger. */
  service_python_fn_interact_manual_advance,

  /** Manual mode. Return the active Cozmo to the charger. */
  service_python_fn_interact_manual_return,

  /** Manual mode. Request faces diversion. */
  service_python_fn_interact_manual_req_diversion_faces,

  /** Manual mode. Request conversation diversion. */
  service_python_fn_interact_manual_req_diversion_converse,

  /** Manual mode. Request wander diversion. */
  service_python_fn_interact_manual_req_diversion_wander,
};

/** The Python service. */
extern struct service* const SERVICE_PYTHON;

#endif // #ifndef SERVICE_PYTHON_H
