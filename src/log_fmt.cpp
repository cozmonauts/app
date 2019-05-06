/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#include <vector>

#include <fmt/core.h>
#include <fmt/format.h>

#include "log.h"

static constexpr auto log_level_name(log_level level) {
  switch (level) {
    case log_level_trace:
      return "TRACE";
    case log_level_debug:
      return "DEBUG";
    case log_level_info:
      return "INFO ";
    case log_level_warn:
      return "WARN ";
    case log_level_error:
      return "ERROR";
    case log_level_fatal:
      return "FATAL";
  }

  return "";
}

extern "C" {

/**
 * A stopgap measure for logging to standard output.
 *
 * @param form The log form
 */
void log__temp_format_and_submit(log_form* form) {
  // A vector of formatting arguments
  std::vector<fmt::basic_format_arg<fmt::format_context>> args_vec;

  // Loop through format arguments
  for (int i = 0; i < form->msg_fmt_args_num; ++i) {
    const auto& arg = form->msg_fmt_args[i];

    // Make format argument based on its type
    switch (arg.type) {
      case log_msg_fmt_arg_type_char:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_char));
        break;
      case log_msg_fmt_arg_type_signed_char:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_signed_char));
        break;
      case log_msg_fmt_arg_type_unsigned_char:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_unsigned_char));
        break;
      case log_msg_fmt_arg_type_short:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_short));
        break;
      case log_msg_fmt_arg_type_unsigned_short:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_unsigned_short));
        break;
      case log_msg_fmt_arg_type_int:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_int));
        break;
      case log_msg_fmt_arg_type_unsigned_int:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_unsigned_int));
        break;
      case log_msg_fmt_arg_type_long:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_long));
        break;
      case log_msg_fmt_arg_type_unsigned_long:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_unsigned_long));
        break;
      case log_msg_fmt_arg_type_long_long:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_long_long));
        break;
      case log_msg_fmt_arg_type_unsigned_long_long:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_unsigned_long_long));
        break;
      case log_msg_fmt_arg_type_float:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_float));
        break;
      case log_msg_fmt_arg_type_double:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_double));
        break;
      case log_msg_fmt_arg_type_long_double:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_long_double));
        break;
      case log_msg_fmt_arg_type_string:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_string));
        break;
      case log_msg_fmt_arg_type_pointer:
        args_vec.push_back(fmt::internal::make_arg<fmt::format_context>(arg.value.as_pointer));
        break;
    }
  }

  // Repack arguments in a form {fmt} likes
  fmt::basic_format_args<fmt::format_context> args(args_vec.data(), args_vec.size());

  // Format the message with these arguments
  auto msg = fmt::vformat(form->msg_fmt, args);

  // Print the whole thing to standard out for now
  fmt::print("{} [{}] {}\n", log_level_name(form->level), form->tag, msg);
}

} // extern "C"
