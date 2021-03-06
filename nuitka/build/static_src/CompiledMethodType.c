//     Copyright 2019, Kay Hayen, mailto:kay.hayen@gmail.com
//
//     Part of "Nuitka", an optimizing Python compiler that is compatible and
//     integrates with CPython, but also works on its own.
//
//     Licensed under the Apache License, Version 2.0 (the "License");
//     you may not use this file except in compliance with the License.
//     You may obtain a copy of the License at
//
//        http://www.apache.org/licenses/LICENSE-2.0
//
//     Unless required by applicable law or agreed to in writing, software
//     distributed under the License is distributed on an "AS IS" BASIS,
//     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//     See the License for the specific language governing permissions and
//     limitations under the License.
//

#include "nuitka/prelude.h"

#include "nuitka/freelists.h"

#include "structmember.h"

static PyObject *Nuitka_Method_get__doc__(struct Nuitka_MethodObject *method, void *closure) {
    PyObject *result = method->m_function->m_doc;

    if (result == NULL) {
        result = Py_None;
    }

    Py_INCREF(result);
    return result;
}

static PyGetSetDef Nuitka_Method_getsets[] = {{(char *)"__doc__", (getter)Nuitka_Method_get__doc__, NULL, NULL},
                                              {NULL}};

#define OFF(x) offsetof(struct Nuitka_MethodObject, x)

static PyMemberDef Nuitka_Method_members[] = {
    {(char *)"im_class", T_OBJECT, OFF(m_class), READONLY | RESTRICTED, (char *)"the class associated with a method"},
    {(char *)"im_func", T_OBJECT, OFF(m_function), READONLY | RESTRICTED,
     (char *)"the function (or other callable) implementing a method"},
    {(char *)"__func__", T_OBJECT, OFF(m_function), READONLY | RESTRICTED,
     (char *)"the function (or other callable) implementing a method"},
    {(char *)"im_self", T_OBJECT, OFF(m_object), READONLY | RESTRICTED,
     (char *)"the instance to which a method is bound; None for unbound method"},
    {(char *)"__self__", T_OBJECT, OFF(m_object), READONLY | RESTRICTED,
     (char *)"the instance to which a method is bound; None for unbound method"},
    {NULL}};

static PyObject *Nuitka_Method_reduce(struct Nuitka_MethodObject *method) {
    PyErr_Format(PyExc_TypeError, "Can't pickle instancemethod objects");

    return NULL;
}

static PyObject *Nuitka_Method_reduce_ex(struct Nuitka_MethodObject *method, PyObject *args) {
    int proto;

    if (!PyArg_ParseTuple(args, "|i:__reduce_ex__", &proto)) {
        return NULL;
    }

    PyErr_Format(PyExc_TypeError, "Can't pickle instancemethod objects");

    return NULL;
}

static PyObject *Nuitka_Method_deepcopy(struct Nuitka_MethodObject *method, PyObject *memo) {
    assert(Nuitka_Method_Check((PyObject *)method));

    static PyObject *module_copy = NULL;
    static PyObject *deepcopy_function = NULL;

    if (module_copy == NULL) {
        module_copy = PyImport_ImportModule("copy");
        CHECK_OBJECT(module_copy);

        deepcopy_function = PyObject_GetAttrString(module_copy, "deepcopy");
        CHECK_OBJECT(deepcopy_function);
    }

    PyObject *object = PyObject_CallFunctionObjArgs(deepcopy_function, method->m_object, memo, NULL);

    if (unlikely(object == NULL)) {
        return NULL;
    }

    return Nuitka_Method_New(method->m_function, object, method->m_class);
}

static PyMethodDef Nuitka_Method_methods[] = {
    {"__reduce__", (PyCFunction)Nuitka_Method_reduce, METH_NOARGS, NULL},
    {"__reduce_ex__", (PyCFunction)Nuitka_Method_reduce_ex, METH_VARARGS, NULL},
    {"__deepcopy__", (PyCFunction)Nuitka_Method_deepcopy, METH_O, NULL},
    {NULL}};

extern PyObject *const_str_plain___name__;

static char const *GET_CLASS_NAME(PyObject *klass) {
    if (klass == NULL) {
        return "?";
    } else {
#if PYTHON_VERSION < 300
        if (PyClass_Check(klass)) {
            return Nuitka_String_AsString(((PyClassObject *)klass)->cl_name);
        }
#endif

        if (!PyType_Check(klass)) {
            klass = (PyObject *)Py_TYPE(klass);
        }

        return ((PyTypeObject *)klass)->tp_name;
    }
}

extern PyObject *const_str_plain___class__;

static char const *GET_INSTANCE_CLASS_NAME(PyObject *instance) {
    PyObject *klass = PyObject_GetAttr(instance, const_str_plain___class__);

    // Fallback to type as this cannot fail.
    if (klass == NULL) {
        CLEAR_ERROR_OCCURRED();

        klass = (PyObject *)Py_TYPE(instance);
        Py_INCREF(klass);
    }

    char const *result = GET_CLASS_NAME(klass);

    Py_DECREF(klass);

    return result;
}

static char const *GET_CALLABLE_DESC(PyObject *object) {
    if (Nuitka_Function_Check(object) || Nuitka_Generator_Check(object) || PyMethod_Check(object) ||
        PyFunction_Check(object) || PyCFunction_Check(object)) {
        return "()";
    }
#if PYTHON_VERSION < 300
    else if (PyClass_Check(object)) {
        return " constructor";
    } else if (PyInstance_Check(object)) {
        return " instance";
    }
#endif
    else {
        return " object";
    }
}

static char const *GET_CALLABLE_NAME(PyObject *object) {
    if (Nuitka_Function_Check(object)) {
        return Nuitka_String_AsString(Nuitka_Function_GetName(object));
    } else if (Nuitka_Generator_Check(object)) {
        return Nuitka_String_AsString(Nuitka_Generator_GetName(object));
    } else if (PyMethod_Check(object)) {
        return PyEval_GetFuncName(PyMethod_GET_FUNCTION(object));
    } else if (PyFunction_Check(object)) {
        return Nuitka_String_AsString(((PyFunctionObject *)object)->func_name);
    }
#if PYTHON_VERSION < 300
    else if (PyInstance_Check(object)) {
        return Nuitka_String_AsString(((PyInstanceObject *)object)->in_class->cl_name);
    } else if (PyClass_Check(object)) {
        return Nuitka_String_AsString(((PyClassObject *)object)->cl_name);
    }
#endif
    else if (PyCFunction_Check(object)) {
        return ((PyCFunctionObject *)object)->m_ml->ml_name;
    } else {
        return Py_TYPE(object)->tp_name;
    }
}

static PyObject *Nuitka_Method_tp_call(struct Nuitka_MethodObject *method, PyObject *args, PyObject *kw) {
    Py_ssize_t arg_count = PyTuple_Size(args);

    if (method->m_object == NULL) {
        if (unlikely(arg_count < 1)) {
            PyErr_Format(
                PyExc_TypeError,
                "unbound compiled_method %s%s must be called with %s instance as first argument (got nothing instead)",
                GET_CALLABLE_NAME((PyObject *)method->m_function), GET_CALLABLE_DESC((PyObject *)method->m_function),
                GET_CLASS_NAME(method->m_class));
            return NULL;
        } else {
            PyObject *self = PyTuple_GET_ITEM(args, 0);
            CHECK_OBJECT(self);

            int result = PyObject_IsInstance(self, method->m_class);

            if (unlikely(result < 0)) {
                return NULL;
            } else if (unlikely(result == 0)) {
                PyErr_Format(PyExc_TypeError,
                             "unbound compiled_method %s%s must be called with %s instance as first argument (got %s "
                             "instance instead)",
                             GET_CALLABLE_NAME((PyObject *)method->m_function),
                             GET_CALLABLE_DESC((PyObject *)method->m_function), GET_CLASS_NAME(method->m_class),
                             GET_INSTANCE_CLASS_NAME((PyObject *)self));

                return NULL;
            }
        }

        return Py_TYPE(method->m_function)->tp_call((PyObject *)method->m_function, args, kw);
    } else {
        return Nuitka_CallMethodFunctionPosArgsKwArgs(method->m_function, method->m_object, &PyTuple_GET_ITEM(args, 0),
                                                      arg_count, kw);
    }
}

static PyObject *Nuitka_Method_tp_descr_get(struct Nuitka_MethodObject *method, PyObject *object, PyObject *klass) {
    // Don't rebind already bound methods.
    if (method->m_object != NULL) {
        Py_INCREF(method);
        return (PyObject *)method;
    }

    if (method->m_class != NULL && klass != NULL) {
        // Quick subclass test, bound methods remain the same if the class is a sub class
        int result = PyObject_IsSubclass(klass, method->m_class);

        if (unlikely(result < 0)) {
            return NULL;
        } else if (result == 0) {
            Py_INCREF(method);
            return (PyObject *)method;
        }
    }

    return Nuitka_Method_New(method->m_function, object, klass);
}

static PyObject *Nuitka_Method_tp_getattro(struct Nuitka_MethodObject *method, PyObject *name) {
    PyObject *descr = _PyType_Lookup(&Nuitka_Method_Type, name);

    if (descr != NULL) {
        if (
#if PYTHON_VERSION < 300
            PyType_HasFeature(Py_TYPE(descr), Py_TPFLAGS_HAVE_CLASS) &&
#endif
            (Py_TYPE(descr)->tp_descr_get != NULL)) {
            return Py_TYPE(descr)->tp_descr_get(descr, (PyObject *)method, (PyObject *)Py_TYPE(method));
        } else {
            Py_INCREF(descr);
            return descr;
        }
    }

    return PyObject_GetAttr((PyObject *)method->m_function, name);
}

static long Nuitka_Method_tp_traverse(struct Nuitka_MethodObject *method, visitproc visit, void *arg) {
    Py_VISIT(method->m_function);
    Py_VISIT(method->m_object);
    Py_VISIT(method->m_class);

    return 0;
}

// tp_repr slot, decide how a function shall be output
static PyObject *Nuitka_Method_tp_repr(struct Nuitka_MethodObject *method) {
    if (method->m_object == NULL) {
#if PYTHON_VERSION < 300
        return PyString_FromFormat("<unbound compiled_method %s.%s>", GET_CLASS_NAME(method->m_class),
                                   Nuitka_String_AsString(method->m_function->m_name));
#else
        return PyUnicode_FromFormat("<compiled_function %s at %p>", Nuitka_String_AsString(method->m_function->m_name),
                                    method->m_function);
#endif
    } else {
        // Note: CPython uses repr of the object, although a comment despises
        // it, we do it for compatibility.
        PyObject *object_repr = PyObject_Repr(method->m_object);

        if (object_repr == NULL) {
            return NULL;
        }
#if PYTHON_VERSION < 300
        else if (!PyString_Check(object_repr)) {
            Py_DECREF(object_repr);
            return NULL;
        }
#else
        else if (!PyUnicode_Check(object_repr)) {
            Py_DECREF(object_repr);
            return NULL;
        }
#endif

#if PYTHON_VERSION < 300
        PyObject *result = PyString_FromFormat("<bound compiled_method %s.%s of %s>", GET_CLASS_NAME(method->m_class),
                                               Nuitka_String_AsString(method->m_function->m_name),
                                               Nuitka_String_AsString_Unchecked(object_repr));
#elif PYTHON_VERSION < 350
        PyObject *result = PyUnicode_FromFormat("<bound compiled_method %s.%s of %s>", GET_CLASS_NAME(method->m_class),
                                                Nuitka_String_AsString(method->m_function->m_name),
                                                Nuitka_String_AsString_Unchecked(object_repr));
#else
        PyObject *result = PyUnicode_FromFormat("<bound compiled_method %s of %s>",
                                                Nuitka_String_AsString(method->m_function->m_qualname),
                                                Nuitka_String_AsString_Unchecked(object_repr));
#endif

        Py_DECREF(object_repr);

        return result;
    }
}

#if PYTHON_VERSION < 300
static int Nuitka_Method_tp_compare(struct Nuitka_MethodObject *a, struct Nuitka_MethodObject *b) {
    if (a->m_function->m_counter < b->m_function->m_counter) {
        return -1;
    } else if (a->m_function->m_counter > b->m_function->m_counter) {
        return 1;
    } else if (a->m_object == b->m_object) {
        return 0;
    } else if (a->m_object == NULL) {
        return -1;
    } else if (b->m_object == NULL) {
        return 1;
    } else {
        return PyObject_Compare(a->m_object, b->m_object);
    }
}
#endif

static PyObject *Nuitka_Method_tp_richcompare(struct Nuitka_MethodObject *a, struct Nuitka_MethodObject *b, int op) {
    if (op != Py_EQ && op != Py_NE) {
        Py_INCREF(Py_NotImplemented);
        return Py_NotImplemented;
    }

    if (Nuitka_Method_Check((PyObject *)a) == false || Nuitka_Method_Check((PyObject *)b) == false) {
        Py_INCREF(Py_NotImplemented);
        return Py_NotImplemented;
    }

    bool b_res = a->m_function->m_counter == b->m_function->m_counter;

    // If the underlying function objects are the same, check the objects, which
    // may be NULL in case of unbound methods, which would be the same again.
    if (b_res) {
        if (a->m_object == NULL) {
            b_res = b->m_object == NULL;
        } else if (b->m_object == NULL) {
            b_res = false;
        } else {
            int res = PyObject_RichCompareBool(a->m_object, b->m_object, Py_EQ);

            b_res = res != 0;
        }
    }

    PyObject *result;

    if (op == Py_EQ) {
        result = BOOL_FROM(b_res);
    } else {
        result = BOOL_FROM(!b_res);
    }

    Py_INCREF(result);
    return result;
}

static long Nuitka_Method_tp_hash(struct Nuitka_MethodObject *method) {
    // Just give the hash of the method function, that ought to be good enough.
    return method->m_function->m_counter;
}

#define MAX_METHOD_FREE_LIST_COUNT 100
static struct Nuitka_MethodObject *free_list_methods = NULL;
static int free_list_methods_count = 0;

static void Nuitka_Method_tp_dealloc(struct Nuitka_MethodObject *method) {
#ifndef __NUITKA_NO_ASSERT__
    // Save the current exception, if any, we must to not corrupt it.
    PyObject *save_exception_type, *save_exception_value;
    PyTracebackObject *save_exception_tb;
    FETCH_ERROR_OCCURRED(&save_exception_type, &save_exception_value, &save_exception_tb);
    RESTORE_ERROR_OCCURRED(save_exception_type, save_exception_value, save_exception_tb);
#endif

    Nuitka_GC_UnTrack(method);

    if (method->m_weakrefs != NULL) {
        PyObject_ClearWeakRefs((PyObject *)method);
    }

    Py_XDECREF(method->m_object);
    Py_XDECREF(method->m_class);

    Py_DECREF((PyObject *)method->m_function);

    /* Put the object into freelist or release to GC */
    releaseToFreeList(free_list_methods, method, MAX_METHOD_FREE_LIST_COUNT);

#ifndef __NUITKA_NO_ASSERT__
    PyThreadState *tstate = PyThreadState_GET();

    assert(tstate->curexc_type == save_exception_type);
    assert(tstate->curexc_value == save_exception_value);
    assert((PyTracebackObject *)tstate->curexc_traceback == save_exception_tb);
#endif
}

static PyObject *Nuitka_Method_tp_new(PyTypeObject *type, PyObject *args, PyObject *kw) {
    PyObject *func;
    PyObject *self;
    PyObject *klass = NULL;

    if (!_PyArg_NoKeywords("instancemethod", kw)) {
        return NULL;
    } else if (!PyArg_UnpackTuple(args, "compiled_method", 2, 3, &func, &self, &klass)) {
        return NULL;
    } else if (!PyCallable_Check(func)) {
        PyErr_Format(PyExc_TypeError, "first argument must be callable");
        return NULL;
    } else {
        if (self == Py_None) {
            self = NULL;
        }

        if (self == NULL && klass == NULL) {
            PyErr_Format(PyExc_TypeError, "unbound methods must have non-NULL im_class");
            return NULL;
        }
    }

    assert(Nuitka_Function_Check(func));

    return Nuitka_Method_New((struct Nuitka_FunctionObject *)func, self, klass);
}

PyTypeObject Nuitka_Method_Type = {
    PyVarObject_HEAD_INIT(NULL, 0) "compiled_method",
    sizeof(struct Nuitka_MethodObject),
    0,
    (destructor)Nuitka_Method_tp_dealloc, /* tp_dealloc */
    0,                                    /* tp_print   */
    0,                                    /* tp_getattr */
    0,                                    /* tp_setattr */
#if PYTHON_VERSION < 300
    (cmpfunc)Nuitka_Method_tp_compare, /* tp_compare */
#else
    0,
#endif
    (reprfunc)Nuitka_Method_tp_repr,         /* tp_repr */
    0,                                       /* tp_as_number */
    0,                                       /* tp_as_sequence */
    0,                                       /* tp_as_mapping */
    (hashfunc)Nuitka_Method_tp_hash,         /* tp_hash */
    (ternaryfunc)Nuitka_Method_tp_call,      /* tp_call */
    0,                                       /* tp_str */
    (getattrofunc)Nuitka_Method_tp_getattro, /* tp_getattro */
    PyObject_GenericSetAttr,                 /* tp_setattro */
    0,                                       /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT |                     /* tp_flags */
#if PYTHON_VERSION < 300
        Py_TPFLAGS_HAVE_WEAKREFS |
#endif
        Py_TPFLAGS_HAVE_GC,
    0,                                                /* tp_doc */
    (traverseproc)Nuitka_Method_tp_traverse,          /* tp_traverse */
    0,                                                /* tp_clear */
    (richcmpfunc)Nuitka_Method_tp_richcompare,        /* tp_richcompare */
    offsetof(struct Nuitka_MethodObject, m_weakrefs), /* tp_weaklistoffset */
    0,                                                /* tp_iter */
    0,                                                /* tp_iternext */
    Nuitka_Method_methods,                            /* tp_methods */
    Nuitka_Method_members,                            /* tp_members */
    Nuitka_Method_getsets,                            /* tp_getset */
    0,                                                /* tp_base */
    0,                                                /* tp_dict */
    (descrgetfunc)Nuitka_Method_tp_descr_get,         /* tp_descr_get */
    0,                                                /* tp_descr_set */
    0,                                                /* tp_dictoffset */
    0,                                                /* tp_init */
    0,                                                /* tp_alloc */
    Nuitka_Method_tp_new,                             /* tp_new */
    0,                                                /* tp_free */
    0,                                                /* tp_is_gc */
    0,                                                /* tp_bases */
    0,                                                /* tp_mro */
    0,                                                /* tp_cache */
    0,                                                /* tp_subclasses */
    0,                                                /* tp_weaklist */
    0,                                                /* tp_del */
    0                                                 /* tp_version_tag */
#if PYTHON_VERSION >= 340
    ,
    0 /* tp_finalizer */
#endif
};

void _initCompiledMethodType(void) { PyType_Ready(&Nuitka_Method_Type); }

PyObject *Nuitka_Method_New(struct Nuitka_FunctionObject *function, PyObject *object, PyObject *klass) {
    struct Nuitka_MethodObject *result;

    allocateFromFreeListFixed(free_list_methods, struct Nuitka_MethodObject, Nuitka_Method_Type);

    if (unlikely(result == NULL)) {
        PyErr_Format(PyExc_RuntimeError, "cannot create method %s", Nuitka_String_AsString(function->m_name));

        return NULL;
    }

    Py_INCREF(function);
    result->m_function = function;

    result->m_object = object;
    Py_XINCREF(object);
    result->m_class = klass;
    Py_XINCREF(klass);

    result->m_weakrefs = NULL;

    Nuitka_GC_Track(result);
    return (PyObject *)result;
}
