/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#define LOG_TAG "python"

#include <stddef.h>

#include <Python.h>

#include "python.h"

#include "../khash.h"
#include "../log.h"
#include "../service.h"

KHASH_MAP_INIT_INT(i2py, PyObject*)

/** Driver code for exec stage of the friends list operation. */
static const char DRIVER_CODE_OP_FRIENDS_LIST_EXEC[] =
  "from cozmonaut.operation.friends_list import OperationFriendsList\n"
  "op = OperationFriendsList(args)\n"
  "op.start()\n";

/** Driver code for stop stage of the friends list operation. */
static const char DRIVER_CODE_OP_FRIENDS_LIST_STOP[] =
  "op = globals()['op']\n"
  "op.stop()\n";

/** Driver code for exec stage of the friends remove operation. */
static const char DRIVER_CODE_OP_FRIENDS_REMOVE_EXEC[] =
  "from cozmonaut.operation.friends_remove import OperationFriendsRemove\n"
  "op = OperationFriendsRemove(args)\n"
  "op.start()\n";

/** Driver code for stop stage of the friends remove operation. */
static const char DRIVER_CODE_OP_FRIENDS_REMOVE_STOP[] =
  "op = globals()['op']\n"
  "op.stop()\n";

/** Driver code for exec stage of the interact operation. */
static const char DRIVER_CODE_OP_INTERACT_EXEC[] =
  "from cozmonaut.operation.interact import OperationInteract\n"
  "op = OperationInteract(args)\n"
  "op.start()\n"
  "globals()['op'] = op\n";

/** Driver code for stop stage of the interact operation. */
static const char DRIVER_CODE_OP_INTERACT_STOP[] =
  "op = globals()['op']\n"
  "op.stop()\n";

/** Driver code for enabling automatic interaction. */
static const char DRIVER_CODE_AUTO_ENABLE[] =
  "op = globals()['op']\n"
  "op.auto_enable()\n";

/** Driver code for disabling automatic interaction. */
static const char DRIVER_CODE_AUTO_DISABLE[] =
  "op = globals()['op']\n"
  "op.auto_disable()\n";

/** Driver code for requesting manual advance. */
static const char DRIVER_CODE_MANUAL_ADVANCE[] =
  "op = globals()['op']\n"
  "op.manual_advance()\n";

/** Driver code for requesting manual return. */
static const char DRIVER_CODE_MANUAL_RETURN[] =
  "op = globals()['op']\n"
  "op.manual_return()\n";

/** Driver code for requesting manual faces diversion. */
static const char DRIVER_CODE_MANUAL_REQ_DIVERSION_FACES[] =
  "op = globals()['op']\n"
  "op.manual_req_diversion_faces()\n";

/** Driver code for requesting manual converse diversion. */
static const char DRIVER_CODE_MANUAL_REQ_DIVERSION_CONVERSE[] =
  "op = globals()['op']\n"
  "op.manual_req_diversion_converse()\n";

/** Driver code for requesting manual wander diversion. */
static const char DRIVER_CODE_MANUAL_REQ_DIVERSION_WANDER[] =
  "op = globals()['op']\n"
  "op.manual_req_diversion_wander()\n";

/** The selected operation. */
static enum service_python_op python__op;

/** Nonzero if an operation is selected. */
static int python__op_selected;

/** Python thread state. */
static __thread PyThreadState* python__thread_state;

//
// base.Monitor class
//
// Part of base extension module.
//

/** An instance of the Monitor class. */
typedef struct {
  PyObject_HEAD

  /** The ID of the associated robot. */
  int robot_id;
} MonitorObject;

static int Monitor_init(MonitorObject* self, PyObject* args, PyObject* kwds) {
  return 0;
}

static void Monitor_dealloc(MonitorObject* self) {
  Py_TYPE(self)->tp_free(self);
}

static PyObject* Monitor_push_battery(MonitorObject* self, PyObject* args) {
  // Unpack battery voltage (no reference)
  double voltage;
  if (!PyArg_ParseTuple(args, "d", &voltage)) {
    // Forward exception
    return NULL;
  }

//LOGI("Battery: {}", _d(voltage));

  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject* Monitor_push_accelerometer(MonitorObject* self, PyObject* args) {
  // Unpack accelerometer reading (no reference)
  double x, y, z;
  if (!PyArg_ParseTuple(args, "ddd", &x, &y, &z)) {
    // Forward exception
    return NULL;
  }

//LOGI("Accelerometer: ({}, {}, {})", _d(x), _d(y), _d(z));

  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject* Monitor_push_gyroscope(MonitorObject* self, PyObject* args) {
  // Unpack gyroscope reading (no reference)
  double x, y, z;
  if (!PyArg_ParseTuple(args, "ddd", &x, &y, &z)) {
    // Forward exception
    return NULL;
  }

//LOGI("Gyroscope: ({}, {}, {})", _d(x), _d(y), _d(z));

  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject* Monitor_push_wheel_speeds(MonitorObject* self, PyObject* args) {
  // Unpack gyroscope reading (no reference)
  double l, r;
  if (!PyArg_ParseTuple(args, "dd", &l, &r)) {
    // Forward exception
    return NULL;
  }

//LOGI("Left wheel: {}", _d(l));
//LOGI("Right wheel: {}", _d(r));

  Py_INCREF(Py_None);
  return Py_None;
}

PyObject* Monitor_getter_delay_battery(MonitorObject* self, PyObject* args) {
  // The delay in seconds (TODO: Make this configurable)
  static const double delay = 3;

  // Create float object for delay (new reference)
  PyObject* delay_battery = PyFloat_FromDouble(delay);
  if (!delay_battery) {
    // Forward exception
    return NULL;
  }

  return delay_battery;
}

PyObject* Monitor_getter_delay_imu(MonitorObject* self, PyObject* args) {
  // The delay in seconds (TODO: Make this configurable)
  static const double delay = 0.1;

  // Create float object for delay (new reference)
  PyObject* delay_imu = PyFloat_FromDouble(delay);
  if (!delay_imu) {
    // Forward exception
    return NULL;
  }

  return delay_imu;
}

PyObject* Monitor_getter_delay_wheel_speeds(MonitorObject* self, PyObject* args) {
  // The delay in seconds (TODO: Make this configurable)
  static const double delay = 0.1;

  // Create float object for delay (new reference)
  PyObject* delay_wheel_speeds = PyFloat_FromDouble(delay);
  if (!delay_wheel_speeds) {
    // Forward exception
    return NULL;
  }

  return delay_wheel_speeds;
}

/** Methods for base.Monitor class. */
static PyMethodDef Monitor_methods[] = {
  {
    .ml_name = "push_battery",
    .ml_meth = (PyCFunction) &Monitor_push_battery,
    .ml_flags = METH_VARARGS,
  },
  {
    .ml_name = "push_accelerometer",
    .ml_meth = (PyCFunction) &Monitor_push_accelerometer,
    .ml_flags = METH_VARARGS,
  },
  {
    .ml_name = "push_gyroscope",
    .ml_meth = (PyCFunction) &Monitor_push_gyroscope,
    .ml_flags = METH_VARARGS,
  },
  {
    .ml_name = "push_wheel_speeds",
    .ml_meth = (PyCFunction) &Monitor_push_wheel_speeds,
    .ml_flags = METH_VARARGS,
  },
  {
  },
};

/** Getters and setters for base.Monitor class. */
static PyGetSetDef Monitor_getset[] = {
  {
    .name = "delay_battery",
    .get = (getter) &Monitor_getter_delay_battery,
  },
  {
    .name = "delay_imu",
    .get = (getter) &Monitor_getter_delay_imu,
  },
  {
    .name = "delay_wheel_speeds",
    .get = (getter) &Monitor_getter_delay_wheel_speeds,
  },
  {
  },
};

/** The Monitor class. */
static PyTypeObject MonitorType = {
  PyVarObject_HEAD_INIT(NULL, 0)
  .tp_name = "base.Module",
  .tp_basicsize = sizeof(MonitorObject),
  .tp_itemsize = 0,
  .tp_dealloc = (destructor) &Monitor_dealloc,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_methods = Monitor_methods,
  .tp_getset = Monitor_getset,
  .tp_init = (initproc) &Monitor_init,
  .tp_new = &PyType_GenericNew,
};

//
// base extension module
//

/** The monitor map. */
static khash_t(i2py)* map_monitor;

static PyObject* base_add_robot(PyObject* self, PyObject* args) {
  // Unpack robot ID (no reference)
  int robot_id;
  if (!PyArg_ParseTuple(args, "i", &robot_id)) {
    // Forward exception
    return NULL;
  }

  // Create a new monitor object (new reference)
  MonitorObject* monitor = (MonitorObject*) PyObject_CallObject((PyObject*) &MonitorType, NULL);
  if (!monitor) {
    // Forward exception
    return NULL;
  }

  // References:
  //  - monitor (keep on success)

  khiter_t it;
  int ret;

  // Key this robot ID into the monitor map
  it = kh_put(i2py, map_monitor, (khint64_t) robot_id, &ret);

  // Store monitor object in monitor map
  kh_val(map_monitor, robot_id) = (PyObject*) monitor;

  // TODO: Clean up the maps

  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject* base_get_monitor(PyObject* self, PyObject* args) {
  // Unpack robot ID (no reference)
  int robot_id;
  if (!PyArg_ParseTuple(args, "i", &robot_id)) {
    // Forward exception
    return NULL;
  }

  // Look up monitor for robot
  khiter_t it = kh_get(i2py, map_monitor, (khint64_t) robot_id);

  // If no mapping exists, return none
  if (it == kh_end(map_monitor)) {
    Py_INCREF(Py_None);
    return Py_None;
  }

  // Get mapped monitor
  MonitorObject* monitor = (MonitorObject*) kh_val(map_monitor, it);

  // Return monitor
  Py_INCREF(monitor);
  return (PyObject*) monitor;
}

/** Methods for base module. */
static PyMethodDef base_methods[] = {
  {
    .ml_name = "add_robot",
    .ml_meth = base_add_robot,
    .ml_flags = METH_VARARGS,
  },
  {
    .ml_name = "get_monitor",
    .ml_meth = base_get_monitor,
    .ml_flags = METH_VARARGS,
  },
  {
  },
};

/** Definition for base module. */
static PyModuleDef base_module = {
  PyModuleDef_HEAD_INIT,
  .m_name = "base",
  .m_size = -1,
  .m_methods = base_methods,
};

/** Initialize base module. */
static PyMODINIT_FUNC PyInit_base() {
  // Ensure Monitor type is ready
  if (PyType_Ready(&MonitorType) < 0) {
    // Forward exception
    return NULL;
  }

  // Create module instance
  PyObject* m = PyModule_Create(&base_module);

  // References:
  //  - m (keep on success)

  // Add Monitor type object to base module (steals reference
  Py_INCREF(&MonitorType);
  if (PyModule_AddObject(m, "Monitor", (PyObject*) &MonitorType) < 0) {
    // References:
    //  - m (keep on success)

    // Release references
    Py_DECREF(m);

    // Forward exception
    return NULL;
  }

  // Initialize monitor map
  map_monitor = kh_init(i2py);

  return m;
}

//
// cstdout extension module
//

/** The sys.stdout write buffer. */
static __thread char* cstdout_buf;

/** The string length of the stdout buffer. */
static __thread size_t cstdout_buf_len;

static PyObject* cstdout_flush(PyObject* self, PyObject* args) {
  // If text is buffered
  if (cstdout_buf) {
    // Log write-buffered text as info
    LOGI("(stdout) {}", _str(cstdout_buf));

    // Clear the write buffer
    free(cstdout_buf);
    cstdout_buf = NULL;
    cstdout_buf_len = 0;
  }

  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject* cstdout_write(PyObject* self, PyObject* args) {
  // Unpack string value (no reference)
  char* string;
  if (!PyArg_ParseTuple(args, "s", &string)) {
    return NULL;
  }

  // Get string length
  size_t string_len = strlen(string);

  // If the string has a newline
  char* nl;
  if ((nl = strchr(string, '\n')) != NULL) {
    // Concatenate write-buffered text with first line of incoming text
    size_t buf_len = cstdout_buf_len + (nl - string);
    char* buf = malloc(buf_len + 1);
    memcpy(buf, cstdout_buf, cstdout_buf_len);
    memcpy(buf + cstdout_buf_len, string, string_len);
    buf[buf_len] = '\0';

    // Clear the write buffer
    free(cstdout_buf);
    cstdout_buf = NULL;
    cstdout_buf_len = 0;

    // Log first line as info
    LOGI("(stdout) {}", _str(buf));

    // Free the concat buffer
    free(buf);

    // If text remains
    if (nl + 1 != string + string_len) {
      // Log intermediary lines
      char* line_begin = nl + 1;
      char* line_end = strchr(line_begin, '\n');
      while (line_end != NULL) {
        // Slice line and log it as info
        *line_end = '\0';
        LOGI("(stdout) {}", _str(line_begin));
        *line_end = '\n';

        // Advance to next line
        line_begin = line_end + 1;
        line_end = strchr(line_begin, '\n');
      }

      // If even more text remains, buffer it
      if (line_begin) {
        cstdout_buf_len = (string + string_len) - line_begin;
        cstdout_buf = malloc(cstdout_buf_len + 1);
        memcpy(cstdout_buf, line_begin, cstdout_buf_len);
        cstdout_buf[cstdout_buf_len] = '\0';
      }
    }
  } else {
    // The string has no newline
    // Buffer the whole string for later
    cstdout_buf = realloc(cstdout_buf, cstdout_buf_len + string_len + 1);
    memcpy(cstdout_buf + cstdout_buf_len, string, string_len);
    cstdout_buf_len += string_len;
    cstdout_buf[cstdout_buf_len] = '\0';
  }

  Py_INCREF(Py_None);
  return Py_None;
}

/** Methods for cstdout module. */
static PyMethodDef cstdout_methods[] = {
  {
    .ml_name = "flush",
    .ml_meth = cstdout_flush,
    .ml_flags = METH_VARARGS,
  },
  {
    .ml_name = "write",
    .ml_meth = cstdout_write,
    .ml_flags = METH_VARARGS,
  },
  {},
};

/** Definition for cstdout module. */
static PyModuleDef cstdout_module = {
  PyModuleDef_HEAD_INIT,
  .m_name = "cstdout",
  .m_size = -1,
  .m_methods = cstdout_methods,
};

/** Initialize cstdout module. */
static PyMODINIT_FUNC PyInit_cstdout() {
  return PyModule_Create(&cstdout_module);
}

//
// cstderr extension module
//

/** The sys.stderr write buffer. */
static __thread char* cstderr_buf;

/** The string length of the stderr buffer. */
static __thread size_t cstderr_buf_len;

static PyObject* cstderr_flush(PyObject* self, PyObject* args) {
  // If text is buffered
  if (cstderr_buf) {
    // Log write-buffered text as an error
    LOGE("(stderr) {}", _str(cstderr_buf));

    // Clear the write buffer
    free(cstderr_buf);
    cstderr_buf = NULL;
    cstderr_buf_len = 0;
  }

  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject* cstderr_write(PyObject* self, PyObject* args) {
  // Unpack string value (no reference)
  char* string;
  if (!PyArg_ParseTuple(args, "s", &string)) {
    return NULL;
  }

  // Get string length
  size_t string_len = strlen(string);

  // If the string has a newline
  char* nl;
  if ((nl = strchr(string, '\n')) != NULL) {
    // Concatenate write-buffered text with first line of incoming text
    size_t buf_len = cstderr_buf_len + (nl - string);
    char* buf = malloc(buf_len + 1);
    memcpy(buf, cstderr_buf, cstderr_buf_len);
    memcpy(buf + cstderr_buf_len, string, string_len);
    buf[buf_len] = '\0';

    // Clear the write buffer
    free(cstderr_buf);
    cstderr_buf = NULL;
    cstderr_buf_len = 0;

    // Log first line as an error
    LOGE("(stderr) {}", _str(buf));

    // Free the concat buffer
    free(buf);

    // If text remains
    if (nl + 1 != string + string_len) {
      // Log intermediary lines
      char* line_begin = nl + 1;
      char* line_end = strchr(line_begin, '\n');
      while (line_end != NULL) {
        // Slice line and log it as an error
        *line_end = '\0';
        LOGE("(stderr) {}", _str(line_begin));
        *line_end = '\n';

        // Advance to next line
        line_begin = line_end + 1;
        line_end = strchr(line_begin, '\n');
      }

      // If even more text remains, buffer it
      if (line_begin) {
        cstderr_buf_len = (string + string_len) - line_begin;
        cstderr_buf = malloc(cstderr_buf_len + 1);
        memcpy(cstderr_buf, line_begin, cstderr_buf_len);
        cstderr_buf[cstderr_buf_len] = '\0';
      }
    }
  } else {
    // The string has no newline
    // Buffer the whole string for later
    cstderr_buf = realloc(cstderr_buf, cstderr_buf_len + string_len + 1);
    memcpy(cstderr_buf + cstderr_buf_len, string, string_len);
    cstderr_buf_len += string_len;
    cstderr_buf[cstderr_buf_len] = '\0';
  }

  Py_INCREF(Py_None);
  return Py_None;
}

/** Methods for cstderr module. */
static PyMethodDef cstderr_methods[] = {
  {
    .ml_name = "flush",
    .ml_meth = cstderr_flush,
    .ml_flags = METH_VARARGS,
  },
  {
    .ml_name = "write",
    .ml_meth = cstderr_write,
    .ml_flags = METH_VARARGS,
  },
  {},
};

/** Definition for cstderr module. */
static PyModuleDef cstderr_module = {
  PyModuleDef_HEAD_INIT,
  .m_name = "cstderr",
  .m_size = -1,
  .m_methods = cstderr_methods,
};

/** Initialize cstderr module. */
static PyMODINIT_FUNC PyInit_cstderr() {
  return PyModule_Create(&cstderr_module);
}

//
// Python Bookkeeping
//

/** Handle any pending exception on the Python VM. */
static void python__handle_exception() {
  // If an exception is not pending
  if (!PyErr_Occurred()) {
    return;
  }

  // Unload the exception (new references)
  PyObject* type;
  PyObject* value;
  PyObject* traceback;
  PyErr_Fetch(&type, &value, &traceback);

  // References:
  //  - type (nullable)
  //  - value (nullable)
  //  - traceback (nullable)

  // Get Unicode representation of type (new reference)
  PyObject* type_repr = PyObject_Repr(type);
  if (!type_repr) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_XDECREF(traceback); // nullable
    Py_XDECREF(value); // nullable
    Py_XDECREF(type); // nullable

    return;
  }

  // References:
  //  - type (nullable)
  //  - value (nullable)
  //  - traceback (nullable)
  //  - type_repr

  // Get Unicode representation of value (new reference)
  PyObject* value_repr = PyObject_Repr(value);
  if (!value_repr) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(type_repr);
    Py_XDECREF(traceback); // nullable
    Py_XDECREF(value); // nullable
    Py_XDECREF(type); // nullable

    return;
  }

  // References:
  //  - type (nullable)
  //  - value (nullable)
  //  - traceback (nullable)
  //  - type_repr
  //  - value_repr

  // Get Unicode representation of traceback (new reference)
  PyObject* traceback_repr = PyObject_Repr(traceback);
  if (!traceback_repr) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(value_repr);
    Py_DECREF(type_repr);
    Py_XDECREF(traceback); // nullable
    Py_XDECREF(value); // nullable
    Py_XDECREF(type); // nullable

    return;
  }

  // References:
  //  - type (nullable)
  //  - value (nullable)
  //  - traceback (nullable)
  //  - type_repr
  //  - value_repr
  //  - traceback_repr

  // Get bytes of Unicode representation of type (new reference)
  PyObject* type_bytes = PyUnicode_AsEncodedString(type_repr, "utf-8", "replace");
  if (!type_bytes) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(traceback_repr);
    Py_DECREF(value_repr);
    Py_DECREF(type_repr);
    Py_XDECREF(traceback); // nullable
    Py_XDECREF(value); // nullable
    Py_XDECREF(type); // nullable

    return;
  }

  // References:
  //  - type (nullable)
  //  - value (nullable)
  //  - traceback (nullable)
  //  - type_repr
  //  - value_repr
  //  - traceback_repr
  //  - type_bytes

  // Get bytes of Unicode representation of value (new reference)
  PyObject* value_bytes = PyUnicode_AsEncodedString(value_repr, "utf-8", "replace");
  if (!value_bytes) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(type_bytes);
    Py_DECREF(traceback_repr);
    Py_DECREF(value_repr);
    Py_DECREF(type_repr);
    Py_XDECREF(traceback); // nullable
    Py_XDECREF(value); // nullable
    Py_XDECREF(type); // nullable

    return;
  }

  // References:
  //  - type (nullable)
  //  - value (nullable)
  //  - traceback (nullable)
  //  - type_repr
  //  - value_repr
  //  - traceback_repr
  //  - type_bytes
  //  - value_bytes

  // Get bytes of Unicode representation of traceback (new reference)
  PyObject* traceback_bytes = PyUnicode_AsEncodedString(traceback_repr, "utf-8", "replace");
  if (!traceback_bytes) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(value_bytes);
    Py_DECREF(type_bytes);
    Py_DECREF(traceback_repr);
    Py_DECREF(value_repr);
    Py_DECREF(type_repr);
    Py_XDECREF(traceback); // nullable
    Py_XDECREF(value); // nullable
    Py_XDECREF(type); // nullable

    return;
  }

  // References:
  //  - type (nullable)
  //  - value (nullable)
  //  - traceback (nullable)
  //  - type_repr
  //  - value_repr
  //  - traceback_repr
  //  - type_bytes
  //  - value_bytes
  //  - traceback_bytes

  // Get string representation of type (no reference)
  char* type_string = PyBytes_AsString(type_bytes);
  if (!type_string) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(value_bytes);
    Py_DECREF(type_bytes);
    Py_DECREF(traceback_repr);
    Py_DECREF(value_repr);
    Py_DECREF(type_repr);
    Py_XDECREF(traceback); // nullable
    Py_XDECREF(value); // nullable
    Py_XDECREF(type); // nullable

    return;
  }

  // Get string representation of value (no reference)
  char* value_string = PyBytes_AsString(value_bytes);
  if (!value_string) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(value_bytes);
    Py_DECREF(type_bytes);
    Py_DECREF(traceback_repr);
    Py_DECREF(value_repr);
    Py_DECREF(type_repr);
    Py_XDECREF(traceback); // nullable
    Py_XDECREF(value); // nullable
    Py_XDECREF(type); // nullable

    return;
  }

  // Get string representation of traceback (no reference)
  char* traceback_string = PyBytes_AsString(traceback_bytes);
  if (!traceback_string) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(value_bytes);
    Py_DECREF(type_bytes);
    Py_DECREF(traceback_repr);
    Py_DECREF(value_repr);
    Py_DECREF(type_repr);
    Py_XDECREF(traceback); // nullable
    Py_XDECREF(value); // nullable
    Py_XDECREF(type); // nullable

    return;
  }

  LOGE("!!!  !!! !!! !!! !!! !!! !!! !!! !!! !!! !!!  !!!");
  LOGE("!!! A Python exception has occurred in C code !!!");
  LOGE("!!!  !!! !!! !!! !!! !!! !!! !!! !!! !!! !!!  !!!");
  LOGE(" -> Type: {}", _str(type_string));
  LOGE(" -> Value: {}", _str(value_string));
  LOGE(" -> Traceback: {}", _str(traceback_string));

  // Release references
  Py_DECREF(value_bytes);
  Py_DECREF(type_bytes);
  Py_XDECREF(traceback_repr);
  Py_XDECREF(value_repr);
  Py_XDECREF(type_repr);

  // References to be stolen:
  //  - type (nullable)
  //  - value (nullable)
  //  - traceback (nullable)

  // Restore the exception, print it, and clear it
  PyErr_Restore(type, value, traceback);
  PyErr_Print();
  PyErr_Clear();
}

/** Append our known paths to the Python VM. */
static void python__append_paths() {
  // Import sys module (borrowed reference)
  PyObject* sys = PyImport_ImportModule("sys");
  if (!sys) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Get the sys.path list (new reference)
  PyObject* path = PyObject_GetAttrString(sys, "path");
  if (!path) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // References:
  //  - path

  // Create Unicode string object for string
  PyObject* str = PyUnicode_FromString("../python/"); // FIXME: Allow this to be specified
  if (!str) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(path);

    return;
  }

  // References:
  //  - path
  //  - str

  // Append string to path
  if (PyList_Append(path, str) < 0) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(str);
    Py_DECREF(path);

    return;
  }

  // Release references
  Py_DECREF(str);
  Py_DECREF(path);
}

//
// Operations
//

/** Execute the friends list operation. */
static void python__op_friends_list_exec() {
  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Create arguments dictionary (new reference)
  PyObject* args = PyDict_New();
  if (!args) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // References
  //  - args

  // Add arguments dictionary to module
  if (PyDict_SetItemString(dict, "args", args) < 0) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(args);

    return;
  }

  // TODO: Append arguments

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_OP_FRIENDS_LIST_EXEC, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(args);

    return;
  }

  // Release references
  Py_DECREF(args);
}

/** Stop the friends list operation. */
static void python__op_friends_list_stop() {
  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_OP_FRIENDS_LIST_STOP, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    return;
  }
}

/** Execute the friends remove operation. */
static void python__op_friends_remove_exec() {
  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Create arguments dictionary (new reference)
  PyObject* args = PyDict_New();
  if (!args) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // References
  //  - args

  // Add arguments dictionary to module
  if (PyDict_SetItemString(dict, "args", args) < 0) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(args);

    return;
  }

  // TODO: Append arguments

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_OP_FRIENDS_REMOVE_EXEC, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(args);

    return;
  }

  // Release references
  Py_DECREF(args);
}

/** Stop the friends remove operation. */
static void python__op_friends_remove_stop() {
  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_OP_FRIENDS_REMOVE_STOP, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    return;
  }
}

/** Execute the interact operation. */
static void python__op_interact_exec() {
  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Create arguments dictionary (new reference)
  PyObject* args = PyDict_New();
  if (!args) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // References
  //  - args

  // Add arguments dictionary to module
  if (PyDict_SetItemString(dict, "args", args) < 0) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(args);

    return;
  }

  // TODO: Append arguments

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_OP_INTERACT_EXEC, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    // Release references
    Py_DECREF(args);

    return;
  }

  // Release references
  Py_DECREF(args);
}

/** Stop the interact operation. */
static void python__op_interact_stop() {
  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return;
  }

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_OP_INTERACT_STOP, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    return;
  }
}

//
// Service Procedures
//

static int python__proc_op_exec(const void* a, void* b) {
  enum service_python_op op = (enum service_python_op) a;

  // If an operation is already selected, then fail
  if (python__op_selected) {
    LOGE("An operation was already selected");
    return 1;
  }

  // Select the operation
  python__op = op;
  python__op_selected = 1;

  // Acquire GIL for all operations
  PyEval_RestoreThread(python__thread_state);

  // Dispatch execution for the operation
  switch (op) {
    case service_python_op_friends_list:
      python__op_friends_list_exec();
      break;
    case service_python_op_friends_remove:
      python__op_friends_remove_exec();
      break;
    case service_python_op_interact:
      python__op_interact_exec();
      break;
  }

  // Release GIL for all operations
  python__thread_state = PyEval_SaveThread();

  return 0;
}

static int python__proc_auto_enable(const void* a, void* b) {
  // Acquire GIL
  PyEval_RestoreThread(python__thread_state);

  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_AUTO_ENABLE, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Release GIL
  python__thread_state = PyEval_SaveThread();

  return 0;
}

static int python__proc_auto_disable(const void* a, void* b) {
  // Acquire GIL
  PyEval_RestoreThread(python__thread_state);

  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_AUTO_DISABLE, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Release GIL
  python__thread_state = PyEval_SaveThread();

  return 0;
}

static int python__proc_manual_advance(const void* a, void* b) {
  // Acquire GIL
  PyEval_RestoreThread(python__thread_state);

  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_MANUAL_ADVANCE, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Release GIL
  python__thread_state = PyEval_SaveThread();

  return 0;
}

static int python__proc_manual_return(const void* a, void* b) {
  // Acquire GIL
  PyEval_RestoreThread(python__thread_state);

  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_MANUAL_RETURN, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Release GIL
  python__thread_state = PyEval_SaveThread();

  return 0;
}

static int python__proc_manual_req_diversion_faces(const void* a, void* b) {
  // Acquire GIL
  PyEval_RestoreThread(python__thread_state);

  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_MANUAL_REQ_DIVERSION_FACES, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Release GIL
  python__thread_state = PyEval_SaveThread();

  return 0;
}

static int python__proc_manual_req_diversion_converse(const void* a, void* b) {
  // Acquire GIL
  PyEval_RestoreThread(python__thread_state);

  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_MANUAL_REQ_DIVERSION_CONVERSE, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Release GIL
  python__thread_state = PyEval_SaveThread();

  return 0;
}

static int python__proc_manual_req_diversion_wander(const void* a, void* b) {
  // Acquire GIL
  PyEval_RestoreThread(python__thread_state);

  // Import the __main__ module (borrowed reference)
  PyObject* main = PyImport_AddModule("__main__");
  if (!main) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Get main module dictionary (borrowed reference)
  PyObject* dict = PyModule_GetDict(main);
  if (!dict) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Run the Python code
  if (!PyRun_String(DRIVER_CODE_MANUAL_REQ_DIVERSION_WANDER, Py_file_input, dict, dict)) {
    // Handle exception
    python__handle_exception();

    return 1;
  }

  // Release GIL
  python__thread_state = PyEval_SaveThread();

  return 0;
}

//
// Service Callbacks
//

static int on_load() {
  // Append extension modules to Python init table
  // This will let us import them from Python code
  PyImport_AppendInittab("base", &PyInit_base);
  PyImport_AppendInittab("cstdout", &PyInit_cstdout);
  PyImport_AppendInittab("cstderr", &PyInit_cstderr);

  // Try to initialize Python interpreter
  Py_Initialize();
  if (!Py_IsInitialized()) {
    LOGE("Unable to initialize Python interpreter");

    // Release GIL
    python__thread_state = PyEval_SaveThread();
    return 1;
  }

  // Release GIL
  python__thread_state = PyEval_SaveThread();

  return 0;
}

static int on_unload() {
  // Acquire GIL
  PyEval_RestoreThread(python__thread_state);

  // Try to clean up Python interpreter
  // It's not an error if this fails, but it might leak resources
  if (Py_FinalizeEx() < 0) {
    LOGW("Unable to clean up Python interpreter");
  }

  return 0;
}

static int on_start() {
  // Print library metadata
  LOGI("Python library metadata follows");
  LOGI("Python {}.{}.{} ({})", _i(PY_MAJOR_VERSION), _i(PY_MINOR_VERSION), _i(PY_MICRO_VERSION), _ptr(PY_VERSION_HEX));
  LOGI("Python build {} {}", _str(Py_GetBuildInfo()), _str(Py_GetCompiler() + 1));
  LOGI("PYTHON_API_STRING={} (compiled)", _str(PYTHON_API_STRING));
  LOGI("PYTHON_ABI_STRING={} (compiled)", _str(PYTHON_ABI_STRING));

  // Acquire GIL
  PyEval_RestoreThread(python__thread_state);

  // Import our custom stdout module (borrowed reference)
  PyObject* cstdout = PyImport_ImportModule("cstdout");
  if (!cstdout) {
    // Handle exception
    python__handle_exception();

    LOGF("Failed to import cstdout");

    // Release GIL
    python__thread_state = PyEval_SaveThread();
    return 1;
  }

  // Import our custom stderr module (borrowed reference)
  PyObject* cstderr = PyImport_ImportModule("cstderr");
  if (!cstderr) {
    // Handle exception
    python__handle_exception();

    LOGF("Failed to import cstderr");

    // Release GIL
    python__thread_state = PyEval_SaveThread();
    return 1;
  }

  // Kill standard input (we don't need it, and it would be weird to leave it)
  if (PySys_SetObject("stdin", NULL) < 0) {
    // Handle exception
    python__handle_exception();

    LOGF("Failed to kill standard input");

    // Release GIL
    python__thread_state = PyEval_SaveThread();
    return 1;
  }

  // Wire up redirected standard output and error
  if (PySys_SetObject("stdout", cstdout) < 0) {
    // Handle exception
    python__handle_exception();

    LOGF("Failed to wire standard output");

    // Release GIL
    python__thread_state = PyEval_SaveThread();
    return 1;
  }
  if (PySys_SetObject("stderr", cstderr) < 0) {
    // Handle exception
    python__handle_exception();

    LOGF("Failed to wire standard error");

    // Release GIL
    python__thread_state = PyEval_SaveThread();
    return 1;
  }

  // Append our paths
  python__append_paths();

  // Release GIL
  python__thread_state = PyEval_SaveThread();
  return 0;
}

static int on_stop() {
  // Acquire GIL for all operations
  PyEval_RestoreThread(python__thread_state);

  // If an operation is selected
  if (python__op_selected) {
    // Dispatch stop for the selected operation
    switch (python__op) {
      case service_python_op_friends_list:
        python__op_friends_list_stop();
        break;
      case service_python_op_friends_remove:
        python__op_friends_remove_stop();
        break;
      case service_python_op_interact:
        python__op_interact_stop();
        break;
    }

    // Clear selected operation
    python__op = 0;
    python__op_selected = 0;
  }

  // Release GIL for all operations
  python__thread_state = PyEval_SaveThread();
  return 0;
}

static int (* proc(int fn))(const void* a, void* b) {
  switch (fn) {
    case service_python_fn_op_exec:
      return &python__proc_op_exec;
    case service_python_fn_interact_auto_enable:
      return &python__proc_auto_enable;
    case service_python_fn_interact_auto_disable:
      return &python__proc_auto_disable;
    case service_python_fn_interact_manual_advance:
      return &python__proc_manual_advance;
    case service_python_fn_interact_manual_return:
      return &python__proc_manual_return;
    case service_python_fn_interact_manual_req_diversion_faces:
      return &python__proc_manual_req_diversion_faces;
    case service_python_fn_interact_manual_req_diversion_converse:
      return &python__proc_manual_req_diversion_converse;
    case service_python_fn_interact_manual_req_diversion_wander:
      return &python__proc_manual_req_diversion_wander;
  }

  return NULL;
}

static struct service_iface iface = {
  .on_load = &on_load,
  .on_unload = &on_unload,
  .on_start = &on_start,
  .on_stop = &on_stop,
  .proc = &proc,
};

struct service* const SERVICE_PYTHON = &(struct service) {
  .name = "python",
  .description = "The Python service hosts the Python VM, the Cozmo SDK, and our script.",
  .iface = &iface,
};
