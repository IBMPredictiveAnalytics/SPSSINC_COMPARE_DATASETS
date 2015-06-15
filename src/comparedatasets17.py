#/***********************************************************************
# * Licensed Materials - Property of IBM 
# *
# * IBM SPSS Products: Statistics Common
# *
# * (C) Copyright IBM Corp. 1989, 2011
# *
# * US Government Users Restricted Rights - Use, duplication or disclosure
# * restricted by GSA ADP Schedule Contract with IBM Corp. 
# ************************************************************************/

from __future__ import with_statement

"""Compare two datasets variable by variable.  It can compare cases and/or variables.
This module requires at least SPSS 17.0.0."""

# history
# 28-aug-2007  - JKP- original version
# 27-nov-2008  workaround for Server-only bug in Dataset class
# 27-nov-2008  add detail logging option
# 15-apr-2009   Unicode tweaks to detail log

__version__ = "2.1.2"
__author__ = "SPSS, JKP"

import random, inspect, codecs, sys, textwrap, os, locale

import spss, spssaux
from spss import CellText
###import wingdbstub  ###debug

if spssaux.getSpssMajorVersion() < 17:
    raise ImportError, "This module requires at least SPSS Statistics 17"

if spss.PyInvokeSpss.IsUTF8mode():
    unistr = unicode
else:
    unistr = str

class DataStep(object):
    def __enter__(self):
        """initialization for with statement"""
        try:
            spss.Submit("EXECUTE")  # temporary fix for 17.0.0/1 for Server bug in Dataset class (105443)
            spss.StartDataStep()
        except:
            spss.Submit("EXECUTE")
            spss.StartDataStep()
        return self
    
    def __exit__(self, type, value, tb):
        spss.EndDataStep()
        return False
    
class NonProcPivotTable(object):
    """Accumulate an object that can be turned into a basic pivot table once a procedure state can be established"""
    
    def __init__(self, omssubtype, outlinetitle="", tabletitle="", caption="", rowdim="", coldim="", columnlabels=[]):
        """omssubtype is the OMS table subtype.
        caption is the table caption.
        tabletitle is the table title.
        columnlabels is a sequence of column labels.
        If columnlabels is empty, this is treated as a one-column table, and the rowlabels are used as the values with
        the label column hidden"""
        
        attributesFromDict(locals())
        self.rowlabels = []
        self.columnvalues = []
        self.rowcount = 0

    def addrow(self, rowlabel=None, cvalues=[]):
        """Append a row labelled rowlabel to the table and set value(s) from cvalues.
        
        rowlabel is a label for the stub.
        cvalues is a sequence of values with the same number of values are there are columns in the table."""
        self.rowcount += 1
        if rowlabel is None:
            self.rowlabels.append(str(self.rowcount))
        else:
            self.rowlabels.append(rowlabel)
        self.columnvalues.extend(cvalues)
        self.rowcount += 1
        
        
    def generate(self):
        """Produce the table assuming that a procedure state is now in effect if it has any rows."""

        if self.rowcount > 0:
            table = spss.BasePivotTable(self.tabletitle, self.omssubtype)
            if self.caption:
                table.Caption(self.caption)
            if self.columnlabels != []:
                table.SimplePivotTable(self.rowdim, self.rowlabels, self.coldim, self.columnlabels, self.columnvalues)
            else:
                table.Append(spss.Dimension.Place.row,"rowdim",hideName=True,hideLabels=True)
                table.Append(spss.Dimension.Place.column,"coldim",hideName=True,hideLabels=True)
                colcat = CellText.String("Message")
                for r in self.rowlabels:
                    cellr = CellText.String(r)
                    table[(cellr, colcat)] = cellr

class Difflog(object):
    """Difference logger: Write case differences to a file"""
    
    def __init__(self, logfile, ds1, ds2):
        """logfile is a filespec or None.  None suppresses all logging.
        ds1 and ds2 are the dataset names to be used for labelling in the log.
        If case comparison is terminated prematurely, there is no guarantee that the log is complete."""
        
        self.logfile = logfile
        if not logfile is None:
            # log file is written in utf-8, which may require transcoding.
            if spss.PyInvokeSpss.IsUTF8mode():
                inputencoding = "unicode_internal"
                self.ls = unicode(os.linesep)
            else:
                inputencoding = locale.getlocale()[1]
                self.ls = os.linesep
            self.f = codecs.EncodedFile(codecs.open(logfile, "wb"), inputencoding, "utf8")
            self.ds1 = ds1
            self.ds2 = ds2
            self.previd = None
            ls = self.ls
            self.f.write("Case Differences.  ds1=%(ds1)s, ds2=%(ds2)s%(ls)s" % locals())
            
    def noCase2(self, case1id):
        """log no ds2 case for case1"""
        
        if not self.logfile is None:
            ls = self.ls
            self.f.write("Case mismatch: No case in ds2 for ds1 id \t%(case1id)s%(ls)s" % locals())

    def noCase1(self, case2id):
        """log no ds1 case for case2"""

        if not self.logfile is None:
            ls = self.ls
            self.f.write("Case mismatch: No case in ds1 for ds2 id \t%(case2id)s%(ls)s" % locals())

    def varDiff(self, caseid, varname, value1, value2):
        """log value difference
        
        caseid is the case id value
        varname is the variable name with a difference
        value1 and value2 are the values in the two datasets"""
        
        if not self.logfile is None:
            ls = self.ls
            if value1 is None:
                value1 = "."
            if value2 is None:
                value2 = "."
            if caseid != self.previd:
                self.f.write(ls)
            self.previd = caseid
            self.f.write("""Value difference: case: %(caseid)s\t variable: %(varname)s\t ds1 value: %(value1)s\t ds2 value: %(value2)s%(ls)s""" % locals())

    def close(self):
        if not self.logfile is None:
            self.f.close()
        
class CompareDatasets(object):
    """Compare cases or variable dictionaries in two datasets"""
    def __init__(self, warnings, ds2, ds1="*", idvar=None, diffcount=None,  variables=None,reportroot=None, 
        logfile=None,
        **kwargs):
        """Compare cases or the variable dictionary in two datasets and create new variables indicating differences.
        
        ds1 and ds2 are names of datasets to compare.  Any outcome variables are added to ds1.
        If ds1 is omitted, the active dataset is assumed and is assigned a name if unnamed.
        The two datasets must be sorted in the same order.
        If idvar is None, cases cannot be compared but the dictionary can.
        diffcount if specified is the name of a new variable to record overall comparison statistics for the case.
          Its value will be sysmis if no matching case was found in ds2; otherwise it is the number of discrepancies found.
        idvar is the name of a case id variable in the two datasets indicating which cases are supposed to be the same.
          Its values should be unique and nonmissing, and both datasets must be sorted in ascending order of this variable.
          If there is no suitable id variable, you can compute one in SPSS from $casenum.  If not supplied, cases cannot be compared.
        variables, if specified, indicates which variables should be compared.  It may be a string or sequence of names.
          By default all variables in common in the two datasets are compared.
          Variable names must match in case in order to be compared.
        reportroot, if specified, is a prefix that will be used for variable names that flag unequal values.  New variables
        will be created with the form "prefix_varname", where varname is the variable to which the outcome applies.
        If prefix_varname is too long for a name or a variable with that name already exists, the name is modified
        into a legal and unique name.
        logfile, if specified causes a detailed changelist to be written to a text file.
        
        Summary output is reported in the Viewer.
        
        Any pending transformations will be executed before the comparison is run if possible.
        
        A DataStep is started at each point neededed but ends on the with block."""
        
        
        del(kwargs)   #ignore any extras
        
        self.warnings = warnings  # proto-pivot table
        if ds1 =="*":
            ds1 = spss.ActiveDataset()  # dataset might still be unnamed
            if ds1 == "":
                ds1 = "*"
        self.ds1 = ds1
        self.ds2 = ds2
        self.diffcount = diffcount
        self.idvar = idvar
        self.logfile = logfile
        if not variables is None:
            self.variables = spssaux._buildvarlist(variables)
        else:
            self.variables = None
        self.reportroot = reportroot
        if reportroot:
            self.unicode = spss.PyInvokeSpss.IsUTF8mode()
            if self.unicode:
                self.ec = codecs.getencoder("utf_8")   # in Unicode mode, must figure var names in bytes of utf-8
        self.reportnames = []
        if self.ds1 == "*":
            dsname = "Active Dataset"
        else:
            dsname = self.ds1
        self.title = "Comparison of Datasets %s and %s" % (dsname, self.ds2)
        if variables:
            self.title += " for Selected Variables"

        with DataStep():
            self.ds1obj = spss.Dataset(self.ds1)
            self.ds1 = self.ds1obj.name    # get the name in case the active dataset was implied
            if self.ds1.lower() == self.ds2.lower():
                raise ValueError("Cannot compare a dataset to itself")
            self.ds2obj = spss.Dataset(self.ds2)
            self.vars1 = [v.name for v in self.ds1obj.varlist]
            self.svars1 = set(self.vars1)
            self.vars2 = [v.name for v in self.ds2obj.varlist]
            self.svars2 = set(self.vars2)
            self.commonvars = self.svars1.intersection(self.svars2)
            if self.variables:
                notcommon = set(self.variables) - self.commonvars
                if notcommon:
                    self.warnings.addrow("Warning: the following requested variables to be compared are not present in both datasets and will be omitted.")
                    self.warnings.addrow(", ".join(sorted(notcommon)))
                    self.variables = list(set(self.variables) - notcommon)
            else:
                sd = self.svars1.symmetric_difference(self.svars2)
                if sd:
                    self.warnings.addrow("Warning: the following variables are present in only one dataset and will be ignored.")
                    self.warnings.addrow(", ".join(sorted(sd)))
                self.variables = sorted(list(self.commonvars))
            if not self.variables:
                raise ValueError,  "There are no variables to compare"
            self.vindex1 = []
            self.vindex2 = []
            self.numvars = len(self.variables)
            for v in self.variables:
                self.vindex1.append(self.ds1obj.varlist[v].index)
                self.vindex2.append(self.ds2obj.varlist[v].index)
            if idvar:
                if diffcount:
                    self.diffindex = len(self.ds1obj)   # location of new difference count variable
                    try:
                        self.ds1obj.varlist.append(diffcount, 0)
                        self.ds1obj.varlist[diffcount].label = "Count of Value Differences for %d Variables" % self.numvars
                        self.ds1obj.varlist[diffcount].format = (5,4,0)
                    except:
                        raise ValueError, "diffcount variable already exists or invalid name: %s" % diffcount
                if reportroot:
                    self.reportstart = len(self.ds1obj)
                    nameset = set([v.name.lower() for v in self.ds1obj.varlist])
                    ij = 0
                    for i in range(self.numvars):
                        if not self.idvar == self.variables[i]:
                            self.ds1obj.varlist.append(self._rptname( i, nameset))
                            self.ds1obj.varlist[self.reportstart + ij].label = "Difference for Variable %s" % self.variables[i]
                            self.ds1obj.varlist[self.reportstart + ij].format = (5,1,0)
                            ij+= 1
                try:
                    self.id1 = self.ds1obj.varlist[idvar].index
                    self.id2 = self.ds2obj.varlist[idvar].index
                except:
                    raise ValueError, "The ID variable specified was not found: %s" % idvar
        
    def cases(self):
        """Compare cases and return count of cases with differences."""
        
        self.casetable = NonProcPivotTable("casecomparison", tabletitle="Comparison of Cases", columnlabels=["Count"])
        if not self.idvar:
            raise ValueError("No ID variable was specified.  Cases cannot be compared.")
        i = 0
        prevcasenum1 = None
        prevcasenum2 = None
        unmatchedKt = 0
        ds2extra = 0
        casediffs = 0
        self.logger = Difflog(self.logfile, self.ds1, self.ds2)
        with DataStep():
            self.ds1obj = spss.Dataset(self.ds1)
            self.ds2obj = spss.Dataset(self.ds2)
            case2 = self.ds2obj.cases[i]
            for casenum, case1 in enumerate(self.ds1obj.cases):
                if case1[self.id1] <= prevcasenum1:
                    raise ValueError, "Duplicate or out of order ID value found in %s.  Processing Stopped" % self.ds1
                prevcasenum1 = case1[self.id1]
                try:
                    i0 = 0
                    while case2[self.id2] < case1[self.id1]:
                        if case2[self.id2] <= prevcasenum2:
                            raise ValueError, "Duplicate or out of order ID value found in %s.  Processing Stopped" % self.ds2
                        prevcasenum2 = case2[self.id2]
                        i+= 1
                        case2 = self.ds2obj.cases[i]
                        if casenum == 0:
                            ds2extra += 1
                        else:
                            ds2extra += (i0 > 0)
                        i0 += 1
                except:
                    pass
                if case1[self.id1]  == case2[self.id2]:
                    diffs =self._valcompare(case1, case2, self.reportroot)
                    diffkt, report = diffs[0], diffs[1:]
                    casediffs += (diffkt > 0)
                    if self.diffcount:
                        self.ds1obj.cases[casenum, self.diffindex] = diffkt
                    if self.reportroot:
                        ij = 0
                        for j, val in enumerate(diffs[1:]):
                            self.ds1obj.cases[casenum, self.reportstart + j] = val
                else:
                    unmatchedKt += 1
                    self.logger.noCase2(case1[self.id1])
            try:
                if case2[self.id2] > case1[self.id1]:
                    ds2extra += 1
                    self.logger.noCase1(case2[self.id2])
                self.ds2obj.cases[i+1]
                ds2extra += 1
            except:
                pass
            
        self.casetable.addrow("Cases in Dataset %s" % self.ds1, ["%d" % (casenum+1)])
        self.casetable.addrow("Cases not Matched with Dataset %s" % self.ds2, ["%d" % unmatchedKt])
        if ds2extra > 0:
            self.casetable.addrow("Dataset %s count of cases not in dataset %s at least" % (self.ds2, self.ds1), ["%d" % ds2extra])
        self.casetable.addrow("Cases with Value Differences", ["%d" % casediffs])
        self.logger.close()
        return casediffs
    
    def close(self):
        """Clean up the data step."""
        with DataStep():
            try:
                del self.ds1obj
                del self.ds2obj
            except:
                pass
        
    # mapping of dictionary method argument names to Dataset attribute names
    attrs = {'varlabel': 'label', 'type': 'type', 'format': 'format', 'valuelabels' : 'valueLabels',
              'missingvalues' : 'missingValues', 'measlevel' : 'measurementLevel', 'attributes' : 'attributes',
              'alignment' : 'alignment', 'columnwidth' : 'columnWidth', 'index' : 'index'}
    
    def dictionaries(self, report=True, type=True, varlabel=True, format=True, valuelabels=True, 
        missingvalues=True, measlevel=True, attributes=True, alignment=False, columnwidth=False,
        index=False, **kwargs):
        """Compare selected variable dictionary information for common variables.
        Accumulate report and return list of variables that differ.
        
        report determines what output appears in the Viewer:
          True, the default, produces a list of properties that differ for each variable
          False produces only an overall summary
          
        vartype compares the variable type
        varlabel compares the variable labels
        varformat compares the variable formats
        valuelabels compares the value labels
        missingvalues compares the missing value definitions
        measlevel compare the measurement levels
        attributes compares the variable attributes.
        alignment compares the variable alignment
        columnwidth compares the column widths
        index compares the variable indexes
        
        By default, all of these properties are compared except for the last three."""
        
        del(kwargs)   # ignore extras
        
        #The following line needs to execute before any variables are created in this function.
        #self.infooptions = inspect.getargvalues(inspect.currentframe())[3]  #current arguments and values
        #self.infooptions.pop('self')
        #self.infooptions.pop('report')

        self.infooptions = locals().copy()
        del(self.infooptions['self'])
        del(self.infooptions['report'])
        caption = ", ".join([k for k,v in self.infooptions.items() if v])
        if caption:
            caption = "\n".join(textwrap.wrap("Comparisons: " + caption, 50))
        self.dicttable = NonProcPivotTable("dictcomparison", tabletitle ="Comparison of Variable Dictionaries",
            caption=caption, columnlabels=["Properties That Differ"])

        diffkt = 0
        difflist = []
        with DataStep():
            self.ds1obj = spss.Dataset(self.ds1)
            self.ds2obj = spss.Dataset(self.ds2)
            for v in sorted(self.variables):
                diffs = self._dicdiffs(self.ds1obj.varlist[v], self.ds2obj.varlist[v])
                if len(diffs) > 0:
                    diffkt += 1
                    difflist.append(v)
                    if report:
                        self.dicttable.addrow(v, [", ".join(diffs)])
        self.dicttable.addrow("Variables with Differences", [diffkt])
        return difflist
    
    def _valcompare(self, case1, case2, reportall):
        """compare selected variables in two cases and return discrepancy count and, optionally, a list of the discrepancies.
        
        If a value is a string, trailing blanks are removed before the comparison.
        Two None's are considered equal.
        case1 and case2 are the two sequences to compare.
        If reportall is True, the return value is a sequence of the difference count followed by the differences.
        Otherwise, it is a sequence of length one containing just the difference count.
        If logging details, a difference line is written for each difference."""

        diffs = [0]
        for v in range(self.numvars):
            if  self.id1 == self.vindex1[v]:
                continue
            val = case1[self.vindex1[v]]
            
            if isinstance(val, basestring):
                val1 = val.rstrip()
                # If first value is a string, the second could be numeric, which would raise an exception.
                # Those values should be considered to be different
                val2 = case2[self.vindex2[v]]
                try:
                    val2 = val2.rstrip()
                    diff = val1 != val2
                except:
                    diff = True
            else:
                val1 = val
                val2 = case2[self.vindex2[v]]
                diff = val1 != val2
                #diff =  val != case2[self.vindex2[v]]
            diffs[0] += diff
            if reportall:
                diffs.append(diff)
            if diff:
                self.logger.varDiff(case1[self.id1], self.variables[v], val1, val2)
        return diffs
    
    def _dicdiffs(self, v1obj, v2obj):
        """compare selected dictionary properties of two variable and return a list of difference types
        
        v1obj and v2obj are Dataset variable objects"""
        
        alldiffs= []
        for k in sorted(CompareDatasets.attrs.keys()):
            if self.infooptions[k]:
                attr1 = getattr(v1obj, CompareDatasets.attrs[k])
                attr2 = getattr(v2obj, CompareDatasets.attrs[k])
                if hasattr(attr1, "data"):           # some Dataset objects have their data in a data attribute but do not implement _eq_
                    if attr1.data != attr2.data:
                        alldiffs.append(k)
                else:
                    if attr1 != attr2:
                        alldiffs.append(k)
        return alldiffs
    
    def _rptname(self, varnum, nameset):
        """Return a unique name for the new variable at index varnum.
        
        nameset is a set of all variable names in the dataset in lower case
        """
        MAXNLEN = 64
        candidatename = self.legalname((self.reportroot + "_" + self.variables[varnum]), MAXNLEN)  #"_"
        while candidatename.lower() in nameset:
            candidatename = self.legalname(candidatename, MAXNLEN-4) + str(random.randint(0,9999))
        self.reportnames.append(candidatename)
        nameset.add(candidatename.lower())
        return candidatename

    def legalname(self, name, maxlength):
        """Return a name truncated to no more than maxlength BYTES.
        
        name is the candidate string
        maxlength is the maximum byte count allowed.  It must be a positive integer.
        
        If name is a (code page) string, truncation is straightforward.  If it is Unicode utf-8,
        the utf-8 byte representation must be used to figure this out but still truncate on a character
        boundary."""
        
        if not self.unicode:
            name =  name[:maxlength]
        else:
            newname = []
            nnlen = 0
            
            # In Unicode mode, length must be calculated in terms of utf-8 bytes
            for c in name:
                c8 = self.ec(c)[0]   # one character in utf-8
                nnlen += len(c8)
                if nnlen <= maxlength:
                    newname.append(c)
                else:
                    break
            name = "".join(newname)
        if name[-1] == "_":
            name = name[:-1]
        return name
    
def attributesFromDict(d):
    """build self attributes from a dictionary d."""
    
    # based on Python Cookbook, 2nd edition 6.18
    
    self = d.pop('self')
    for name, value in d.iteritems():
        setattr(self, name, value)
