#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <math.h>
#include <stddef.h>
#include <string.h>

/*
 * Exact Stage-5 0.25 ms prefix recurrence hot loop.
 *
 * The Python reference retains all segment-boundary support/allocation/loaded
 * command work.  This function owns only the 20 sequential physical substeps
 * within one 5 ms segment, over an independent candidate batch.  Arrays are
 * float64 C-contiguous buffers and are updated in place.
 */

enum {
    C_K = 0,
    C_D = 3,
    C_MASS = 6,
    C_REST_X = 9,
    C_REST_THETA = 12,
    C_BETA = 15,
    C_SOFT_LOWER = 26,
    C_SOFT_UPPER = 28,
    C_PLANE_X = 30,
    C_PLANE_Z = 33,
    C_AXIS = 36,
    C_KR = 39,
    C_DR = 40,
    C_INERTIA = 41,
    C_SOFT_MARGIN = 42,
    C_SOFT_BOUNDARY_TORQUE = 43,
    C_SOFT_DAMPING = 44,
    C_THIGH_LENGTH = 45,
    C_CUFF_DISTANCE = 46,
    C_CUFF_OFFSET = 47,
    C_DT = 48,
    C_LENGTH = 49
};

enum {
    TRACE_STATE = 0,
    TRACE_X = 4,
    TRACE_U = 7,
    TRACE_THETA = 10,
    TRACE_OMEGA = 13,
    TRACE_FORCE_WORLD = 16,
    TRACE_MOMENT_WORLD = 19,
    TRACE_WIDTH = 22
};

typedef struct {
    Py_buffer view;
    double *data;
} DoubleBuffer;

static int acquire_double_buffer(
    PyObject *object,
    DoubleBuffer *buffer,
    int writable,
    Py_ssize_t minimum_values,
    const char *name
) {
    int flags = PyBUF_C_CONTIGUOUS | PyBUF_FORMAT;
    if (writable) {
        flags |= PyBUF_WRITABLE;
    }
    memset(buffer, 0, sizeof(*buffer));
    if (PyObject_GetBuffer(object, &buffer->view, flags) < 0) {
        return -1;
    }
    if (buffer->view.itemsize != (Py_ssize_t)sizeof(double)
        || buffer->view.format == NULL
        || strcmp(buffer->view.format, "d") != 0
        || buffer->view.len < minimum_values * (Py_ssize_t)sizeof(double)) {
        PyErr_Format(
            PyExc_ValueError,
            "%s must be a C-contiguous float64 buffer with at least %zd values",
            name,
            minimum_values
        );
        PyBuffer_Release(&buffer->view);
        memset(buffer, 0, sizeof(*buffer));
        return -1;
    }
    buffer->data = (double *)buffer->view.buf;
    return 0;
}

static void release_buffer(DoubleBuffer *buffer) {
    if (buffer->view.obj != NULL) {
        PyBuffer_Release(&buffer->view);
        memset(buffer, 0, sizeof(*buffer));
    }
}

static void mat_vec(const double *matrix, const double *vector, double *result) {
    for (int row = 0; row < 3; ++row) {
        result[row] = (
            matrix[3 * row] * vector[0]
            + matrix[3 * row + 1] * vector[1]
            + matrix[3 * row + 2] * vector[2]
        );
    }
}

static void mat_transpose_vec(
    const double *matrix,
    const double *vector,
    double *result
) {
    for (int col = 0; col < 3; ++col) {
        result[col] = (
            matrix[col] * vector[0]
            + matrix[3 + col] * vector[1]
            + matrix[6 + col] * vector[2]
        );
    }
}

static void cross3(const double *left, const double *right, double *result) {
    result[0] = left[1] * right[2] - left[2] * right[1];
    result[1] = left[2] * right[0] - left[0] * right[2];
    result[2] = left[0] * right[1] - left[1] * right[0];
}

static double dot3(const double *left, const double *right) {
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2];
}

static void geometry(
    double q1,
    double q2,
    const double *constants,
    double *jacobian,
    double *rotation
) {
    const double *plane_x = constants + C_PLANE_X;
    const double *plane_z = constants + C_PLANE_Z;
    const double *axis = constants + C_AXIS;
    const double phi = q1 - q2;
    const double sin_q1 = sin(q1);
    const double cos_q1 = cos(q1);
    const double sin_phi = sin(phi);
    const double cos_phi = cos(phi);
    double e1_perp[3];
    double shank_perp[3];
    for (int component = 0; component < 3; ++component) {
        e1_perp[component] = (
            -sin_q1 * plane_x[component] + cos_q1 * plane_z[component]
        );
        shank_perp[component] = (
            -sin_phi * plane_x[component] + cos_phi * plane_z[component]
        );
        jacobian[2 * component] = (
            constants[C_THIGH_LENGTH] * e1_perp[component]
            + constants[C_CUFF_DISTANCE] * shank_perp[component]
        );
        jacobian[2 * component + 1] = (
            -constants[C_CUFF_DISTANCE] * shank_perp[component]
        );
    }
    const double cuff_angle = phi - constants[C_CUFF_OFFSET];
    const double sin_cuff = sin(cuff_angle);
    const double cos_cuff = cos(cuff_angle);
    for (int row = 0; row < 3; ++row) {
        rotation[3 * row] = (
            cos_cuff * plane_x[row] + sin_cuff * plane_z[row]
        );
        rotation[3 * row + 1] = axis[row];
        rotation[3 * row + 2] = (
            -sin_cuff * plane_x[row] + cos_cuff * plane_z[row]
        );
    }
}

static double soft_limit_component(
    double q,
    double dq,
    double lower,
    double upper,
    const double *constants
) {
    const double margin = constants[C_SOFT_MARGIN];
    if (q < lower) {
        const double z = (lower - q) / margin;
        const double damping_velocity = (-dq > 0.0) ? -dq : 0.0;
        return (
            constants[C_SOFT_BOUNDARY_TORQUE] * z * z * z
            + constants[C_SOFT_DAMPING] * z * z * damping_velocity
        );
    }
    if (q > upper) {
        const double z = (q - upper) / margin;
        const double damping_velocity = (dq > 0.0) ? dq : 0.0;
        return (
            -constants[C_SOFT_BOUNDARY_TORQUE] * z * z * z
            - constants[C_SOFT_DAMPING] * z * z * damping_velocity
        );
    }
    return 0.0;
}

static void human_dynamics(
    const double *state,
    const double *action,
    const double *constants,
    double *derivative
) {
    const double *beta = constants + C_BETA;
    const double q1 = state[0];
    const double q2 = state[1];
    const double dq1 = state[2];
    const double dq2 = state[3];
    const double phi = q1 - q2;
    const double cosine = cos(q2);
    const double sine = sin(q2);
    double zero0 = (
        beta[2] * sine * (-2.0 * dq1 * dq2 + dq2 * dq2)
        + beta[3] * cos(q1)
        + beta[4] * cos(phi)
        + beta[5] * q1
        - beta[7]
        + beta[9] * dq1
    );
    double zero1 = (
        beta[2] * sine * dq1 * dq1
        - beta[4] * cos(phi)
        + beta[6] * q2
        - beta[8]
        + beta[10] * dq2
    );
    zero0 -= soft_limit_component(
        q1,
        dq1,
        constants[C_SOFT_LOWER],
        constants[C_SOFT_UPPER],
        constants
    );
    zero1 -= soft_limit_component(
        q2,
        dq2,
        constants[C_SOFT_LOWER + 1],
        constants[C_SOFT_UPPER + 1],
        constants
    );
    const double mass00 = beta[0] + 2.0 * beta[2] * cosine;
    const double mass01 = -(beta[1] + beta[2] * cosine);
    const double mass11 = beta[1];
    const double rhs0 = action[0] - zero0;
    const double rhs1 = action[1] - zero1;
    const double determinant = mass00 * mass11 - mass01 * mass01;
    derivative[0] = dq1;
    derivative[1] = dq2;
    derivative[2] = (mass11 * rhs0 - mass01 * rhs1) / determinant;
    derivative[3] = (mass00 * rhs1 - mass01 * rhs0) / determinant;
}

static void human_rk4(
    double *state,
    const double *action,
    const double *constants
) {
    const double dt = constants[C_DT];
    double k1[4];
    double k2[4];
    double k3[4];
    double k4[4];
    double temporary[4];
    human_dynamics(state, action, constants, k1);
    for (int index = 0; index < 4; ++index) {
        temporary[index] = state[index] + 0.5 * dt * k1[index];
    }
    human_dynamics(temporary, action, constants, k2);
    for (int index = 0; index < 4; ++index) {
        temporary[index] = state[index] + 0.5 * dt * k2[index];
    }
    human_dynamics(temporary, action, constants, k3);
    for (int index = 0; index < 4; ++index) {
        temporary[index] = state[index] + dt * k3[index];
    }
    human_dynamics(temporary, action, constants, k4);
    for (int index = 0; index < 4; ++index) {
        state[index] = state[index] + dt * (
            k1[index] + 2.0 * k2[index] + 2.0 * k3[index] + k4[index]
        ) / 6.0;
    }
}

static void transform_interface_state(
    const double *next_rotation,
    const double *old_rotation,
    const double *rest_x,
    const double *rest_theta,
    double *x,
    double *u,
    double *theta,
    double *omega
) {
    double frame[9];
    for (int row = 0; row < 3; ++row) {
        for (int col = 0; col < 3; ++col) {
            frame[3 * row + col] = (
                next_rotation[row] * old_rotation[col]
                + next_rotation[3 + row] * old_rotation[3 + col]
                + next_rotation[6 + row] * old_rotation[6 + col]
            );
        }
    }
    double source[3];
    double result[3];
    for (int component = 0; component < 3; ++component) {
        source[component] = x[component] + rest_x[component];
    }
    mat_vec(frame, source, result);
    for (int component = 0; component < 3; ++component) {
        x[component] = result[component] - rest_x[component];
    }
    mat_vec(frame, u, result);
    memcpy(u, result, 3 * sizeof(double));
    for (int component = 0; component < 3; ++component) {
        source[component] = theta[component] + rest_theta[component];
    }
    mat_vec(frame, source, result);
    for (int component = 0; component < 3; ++component) {
        theta[component] = result[component] - rest_theta[component];
    }
    mat_vec(frame, omega, result);
    memcpy(omega, result, 3 * sizeof(double));
}

static void propagate_candidate_substep(
    double *state,
    double *x,
    double *u,
    double *theta,
    double *omega,
    double *rotation,
    double *jacobian,
    const double *drive_world,
    const double *angular_drive_world,
    const double *constants,
    double *force_world_out,
    double *moment_world_out
) {
    const double dt = constants[C_DT];
    const double *k = constants + C_K;
    const double *d = constants + C_D;
    const double *mass = constants + C_MASS;
    const double *rest_x = constants + C_REST_X;
    const double *rest_theta = constants + C_REST_THETA;
    double drive_human[3];
    double angular_drive_human[3];
    mat_transpose_vec(rotation, drive_world, drive_human);
    mat_transpose_vec(rotation, angular_drive_world, angular_drive_human);
    for (int component = 0; component < 3; ++component) {
        const double acceleration = (
            drive_human[component]
            - k[component] * (x[component] - rest_x[component])
            - d[component] * u[component]
        ) / mass[component];
        u[component] += dt * acceleration;
        x[component] += dt * u[component];
        const double angular_acceleration = (
            angular_drive_human[component]
            - constants[C_KR] * (theta[component] - rest_theta[component])
            - constants[C_DR] * omega[component]
        ) / constants[C_INERTIA];
        omega[component] += dt * angular_acceleration;
        theta[component] += dt * omega[component];
    }
    double force_human[3];
    double couple_human[3];
    double arm_human[3];
    double arm_cross_force[3];
    double moment_human[3];
    for (int component = 0; component < 3; ++component) {
        force_human[component] = (
            k[component] * (x[component] - rest_x[component])
            + d[component] * u[component]
        );
        couple_human[component] = (
            constants[C_KR] * (theta[component] - rest_theta[component])
            + constants[C_DR] * omega[component]
        );
        arm_human[component] = x[component] + rest_x[component];
    }
    cross3(arm_human, force_human, arm_cross_force);
    for (int component = 0; component < 3; ++component) {
        moment_human[component] = couple_human[component] + arm_cross_force[component];
    }
    mat_vec(rotation, force_human, force_world_out);
    mat_vec(rotation, moment_human, moment_world_out);
    double action[2];
    action[0] = (
        jacobian[0] * force_world_out[0]
        + jacobian[2] * force_world_out[1]
        + jacobian[4] * force_world_out[2]
    );
    action[1] = (
        jacobian[1] * force_world_out[0]
        + jacobian[3] * force_world_out[1]
        + jacobian[5] * force_world_out[2]
    );
    const double moment_axis = dot3(moment_world_out, constants + C_AXIS);
    action[0] -= moment_axis;
    action[1] += moment_axis;
    human_rk4(state, action, constants);
    double next_jacobian[6];
    double next_rotation[9];
    geometry(state[0], state[1], constants, next_jacobian, next_rotation);
    transform_interface_state(
        next_rotation,
        rotation,
        rest_x,
        rest_theta,
        x,
        u,
        theta,
        omega
    );
    memcpy(rotation, next_rotation, 9 * sizeof(double));
    memcpy(jacobian, next_jacobian, 6 * sizeof(double));
}

static PyObject *propagate_segment(PyObject *self, PyObject *args) {
    (void)self;
    if (PyTuple_Size(args) != 12) {
        PyErr_SetString(
            PyExc_TypeError,
            "propagate_segment requires 12 positional arguments"
        );
        return NULL;
    }
    const long substeps = PyLong_AsLong(PyTuple_GetItem(args, 10));
    if (substeps <= 0 || PyErr_Occurred()) {
        PyErr_SetString(PyExc_ValueError, "substeps must be a positive integer");
        return NULL;
    }
    DoubleBuffer states = {0};
    DoubleBuffer x = {0};
    DoubleBuffer u = {0};
    DoubleBuffer theta = {0};
    DoubleBuffer omega = {0};
    DoubleBuffer rotation = {0};
    DoubleBuffer jacobian = {0};
    DoubleBuffer drive = {0};
    DoubleBuffer angular_drive = {0};
    DoubleBuffer constants = {0};
    DoubleBuffer trace = {0};
    PyObject *trace_object = PyTuple_GetItem(args, 11);
    int ok = -1;
    if (acquire_double_buffer(PyTuple_GetItem(args, 0), &states, 1, 4, "states") < 0) goto cleanup;
    if (states.view.len % (4 * (Py_ssize_t)sizeof(double)) != 0) {
        PyErr_SetString(PyExc_ValueError, "states size must be divisible by four");
        goto cleanup;
    }
    const Py_ssize_t count = states.view.len / (4 * (Py_ssize_t)sizeof(double));
    if (acquire_double_buffer(PyTuple_GetItem(args, 1), &x, 1, count * 3, "x") < 0) goto cleanup;
    if (acquire_double_buffer(PyTuple_GetItem(args, 2), &u, 1, count * 3, "u") < 0) goto cleanup;
    if (acquire_double_buffer(PyTuple_GetItem(args, 3), &theta, 1, count * 3, "theta") < 0) goto cleanup;
    if (acquire_double_buffer(PyTuple_GetItem(args, 4), &omega, 1, count * 3, "omega") < 0) goto cleanup;
    if (acquire_double_buffer(PyTuple_GetItem(args, 5), &rotation, 1, count * 9, "rotation") < 0) goto cleanup;
    if (acquire_double_buffer(PyTuple_GetItem(args, 6), &jacobian, 1, count * 6, "jacobian") < 0) goto cleanup;
    if (acquire_double_buffer(PyTuple_GetItem(args, 7), &drive, 0, count * 3, "drive") < 0) goto cleanup;
    if (acquire_double_buffer(PyTuple_GetItem(args, 8), &angular_drive, 0, count * 3, "angular_drive") < 0) goto cleanup;
    if (acquire_double_buffer(PyTuple_GetItem(args, 9), &constants, 0, C_LENGTH, "constants") < 0) goto cleanup;
    if (trace_object != Py_None) {
        if (acquire_double_buffer(
            trace_object,
            &trace,
            1,
            (Py_ssize_t)substeps * count * TRACE_WIDTH,
            "trace"
        ) < 0) goto cleanup;
    }
    Py_BEGIN_ALLOW_THREADS
    for (long step = 0; step < substeps; ++step) {
        for (Py_ssize_t candidate = 0; candidate < count; ++candidate) {
            double force_world[3];
            double moment_world[3];
            double *state_i = states.data + 4 * candidate;
            double *x_i = x.data + 3 * candidate;
            double *u_i = u.data + 3 * candidate;
            double *theta_i = theta.data + 3 * candidate;
            double *omega_i = omega.data + 3 * candidate;
            propagate_candidate_substep(
                state_i,
                x_i,
                u_i,
                theta_i,
                omega_i,
                rotation.data + 9 * candidate,
                jacobian.data + 6 * candidate,
                drive.data + 3 * candidate,
                angular_drive.data + 3 * candidate,
                constants.data,
                force_world,
                moment_world
            );
            if (trace.data != NULL) {
                double *row = trace.data + (
                    ((Py_ssize_t)step * count + candidate) * TRACE_WIDTH
                );
                memcpy(row + TRACE_STATE, state_i, 4 * sizeof(double));
                memcpy(row + TRACE_X, x_i, 3 * sizeof(double));
                memcpy(row + TRACE_U, u_i, 3 * sizeof(double));
                memcpy(row + TRACE_THETA, theta_i, 3 * sizeof(double));
                memcpy(row + TRACE_OMEGA, omega_i, 3 * sizeof(double));
                memcpy(row + TRACE_FORCE_WORLD, force_world, 3 * sizeof(double));
                memcpy(row + TRACE_MOMENT_WORLD, moment_world, 3 * sizeof(double));
            }
        }
    }
    Py_END_ALLOW_THREADS
    ok = 0;

cleanup:
    release_buffer(&trace);
    release_buffer(&constants);
    release_buffer(&angular_drive);
    release_buffer(&drive);
    release_buffer(&jacobian);
    release_buffer(&rotation);
    release_buffer(&omega);
    release_buffer(&theta);
    release_buffer(&u);
    release_buffer(&x);
    release_buffer(&states);
    if (ok < 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
    {
        "propagate_segment",
        propagate_segment,
        METH_VARARGS,
        "Propagate one candidate batch through one exact prefix segment."
    },
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "_prefix_native",
    "Stage-5 exact native prefix recurrence.",
    -1,
    methods
};

PyMODINIT_FUNC PyInit__prefix_native(void) {
    return PyModule_Create(&module);
}
