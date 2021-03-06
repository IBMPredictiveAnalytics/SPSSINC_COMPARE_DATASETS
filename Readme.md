# SPSSINC COMPARE DATASETS
## Compare two open datasets.
 This procedure compares two open datasets. You can specify whether the comparison includes the case data, the variable properties or both.

---
Requirements
----
- IBM SPSS Statistics 18 or later and the corresponding IBM SPSS Statistics-Integration Plug-in for Python.

Note: For users with IBM SPSS Statistics versions 19, 20 or 21, the SPSSINC COMPARE DATASETS extension is installed as part of IBM SPSS Statistics-Essentials for Python. For users with IBM SPSS Statistics version 21 or higher, consider using the built-in COMPARE DATASETS command.

---
Installation intructions
----
1. Open IBM SPSS Statistics
2. Navigate to Utilities -> Extension Bundles -> Download and Install Extension Bundles
3. Search for the name of the extension and click Ok. Your extension will be available.

---
Tutorial
----
Compare either or both of the cases and variable dictionaries of two datasets.
As of Statistics version 21, the built-in command COMPARE DATASETS can be
used for this purpose.


SPSSINC COMPARE DATASETS DS1=*primary datasetname*^&#42; DS2=*secondary datasetname*^&#42;  
VARIABLES=*variables*  

/DATA ID=*id variable* DIFFCOUNT=*variable* ROOTNAME=*root name* LOGFILE="*filespec*"

/DICTIONARY NONE or MEASLEVEL TYPE VARLABEL VALUELABELS MISSINGVALUES
ATTRIBUTES FORMAT ALIGNMENT COLUMNWIDTH INDEX

HELP

^&#42; Required  
^&#42;&#42; Default

SPSSINC COMPARE DATASETS /HELP displays this text and does nothing else.

Examples:
Compare cases and dictionaries in datasets FIRST and SECOND based on case id variable idvar:
```
SPSSINC COMPARE DATASETS DS1=FIRST DS2=SECOND /DATA ID=idvar DIFFCOUNT=diffs.
```
Compare dictionaries only including all variable properties except alignment, columnwidth, and index:
```
SPSSINC COMPARE DATASETS DS1=FIRST DS2=SECOND.
```
Compare cases only for selected variables:
```
SPSSINC COMPARE DATASETS DS1=FIRST DS2=SECOND VARIABLES=x y z /DICTIONARY NONE.
```
The letter case of dataset and variable names must match the case in SPSS.

If **VARIABLES** is specified, only the selected variables are compared
for both data values and dictionary properties.

DATA
----
If ID is specified, cases are compared.

The cases in both datasets must be sorted by the id variable if cases are compared.
Result variables must not already exist in the dataset.  They are added to the primary dataset.
If **DIFFCOUNT** is specified, the variable contains a count of the number of variable differences in the case.
If **ROOTNAME** is specified, new variables of the form *rootname_variable name* are created with values 0 or 1 according to whether the values match or not.

When a case does not match on the id variable, result variable values are sysmis.

Specify **LOGFILE** to create a text file listing the ids of all cases present in only one dataset and
all values of the selected variables that differ between the two datasets.  The log file is written
in the utf-8 encoding without a BOM (Byte Order Mark).


DICTIONARY
----------
If NONE is NOT specified, dictionaries are compared.
If dictionaries are compared, all properties except alignment, columnwidth, and index are included
by default.
If properties are specified, only those properties are compared.

---
License
----

- Apache 2.0
                              
Contributors
----

  - IBM SPSS
