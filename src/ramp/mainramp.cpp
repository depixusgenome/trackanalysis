//#include<stdio.h>
//#include<stdlib.h>
//#include <Python.h>
//#include<iostream>
#include<cstdlib>
//int main(int argc, char *argv[])
int main()
{

  /*
  wchar_t *program = Py_DecodeLocale(argv[0], NULL);
  if (program == NULL) {
    fprintf(stderr, "Fatal error: cannot decode argv[0]\n");
    exit(1);
  }
  Py_SetProgramName(program);
  Py_Initialize();
  PyObject* sysPath = PySys_GetObject("path");
  PyObject* addPath = PyBytes_FromString("/home/david/miniconda3/lib/python3.5/site-packages/");
  PyList_Insert(sysPath,0,addPath);
  //PySys_SetPath(L"/home/david/miniconda3/lib/python3.5/site-packages/");
  
  //PyRun_SimpleString("import runrampapp; print('hello')");
  PyRun_SimpleString("import numpy;print('hello')");
  Py_Finalize();
  PyMem_RawFree(program);
  */
  system("./runrampapp.py rampapp.MyDisplay");
  return 0;
}
