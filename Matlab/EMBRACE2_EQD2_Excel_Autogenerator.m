classdef EMBRACE2_EQD2_Excel_Autogenerator < matlab.apps.AppBase
    % EMBRACE2_EQD2_Excel_Autogenerator
    %
    % One-click DVH TXT -> populated EQD2 Excel workbook
    %
    % REQUIRED TEMPLATE:
    %   EQD2_with_tolerances_090126.xlsx
    %
    % Keep the template in the same folder as this .m file,
    % OR anywhere on the MATLAB path.
    %
    % MATLAB R2024b
    %
    % Current structure mapping:
    %   GTVres              -> Volume, D98
    %   CTV_HR              -> Volume, D98, D90, D50
    %   CTV_IR              -> Volume, D98, D90
    %   Bladder             -> Volume, D0.1cc, D2cc
    %   Rectum              -> Volume, D0.1cc, D2cc
    %   Colon_Sigmoid       -> Volume, D0.1cc, D2cc
    %   Bowel               -> Volume, D0.1cc, D2cc
    %
    % Fraction columns:
    %   Fx1 = C
    %   Fx2 = D
    %   Fx3 = E
    %   Fx4 = F
    %   Fx5 = G
    %   Fx6 = H

    properties (Access = public)
        UIFigure matlab.ui.Figure
        MainGrid matlab.ui.container.GridLayout

        HeaderPanel matlab.ui.container.Panel
        HeaderGrid matlab.ui.container.GridLayout
        UFLabel matlab.ui.control.Label
        InstituteLabel matlab.ui.control.Label
        HeaderTagline matlab.ui.control.Label

        TitleLabel matlab.ui.control.Label
        SubtitleLabel matlab.ui.control.Label

        WorkflowPanel matlab.ui.container.Panel
        WorkflowGrid matlab.ui.container.GridLayout
        Step1Label matlab.ui.control.Label
        Arrow1Label matlab.ui.control.Label
        Step2Label matlab.ui.control.Label
        Arrow2Label matlab.ui.control.Label
        Step3Label matlab.ui.control.Label

        InputPanel matlab.ui.container.Panel
        InputGrid matlab.ui.container.GridLayout
        SelectButton matlab.ui.control.Button
        FileInfoGrid matlab.ui.container.GridLayout
        FileNameLabel matlab.ui.control.Label
        PatientLabel matlab.ui.control.Label
        PatientIDLabel matlab.ui.control.Label
        PlanLabel matlab.ui.control.Label
        FractionLabel matlab.ui.control.Label

        LogPanel matlab.ui.container.Panel
        LogGrid matlab.ui.container.GridLayout
        LogHeaderLabel matlab.ui.control.Label
        ClearLogButton matlab.ui.control.Button
        DetailsArea matlab.ui.control.TextArea

        NotesPanel matlab.ui.container.Panel
        NotesGrid matlab.ui.container.GridLayout
        NotesTitle matlab.ui.control.Label
        NotesLabel matlab.ui.control.Label

        FooterPanel matlab.ui.container.Panel
        FooterGrid matlab.ui.container.GridLayout
        FooterLeft matlab.ui.control.Label
        FooterRight matlab.ui.control.Label
    end

    properties (Access = private)
        UFBlue = [0.0000 0.1294 0.4118]      % #0021A5-ish deep blue
        UFDarkBlue = [0.0000 0.1804 0.3765]  % dark institutional blue
        UFOrange = [0.9804 0.2902 0.0000]    % #FA4B00-ish orange
        LightBlue = [0.945 0.970 0.990]
        BorderGray = [0.82 0.85 0.88]
        TextGray = [0.18 0.22 0.30]
    end

    methods (Access = private)

        function startupFcn(app)
            app.appendLog("Ready. Select a DVH TXT file to begin.");
        end


        function selectAndProcess(app, ~)

            [file, folder] = uigetfile( ...
                {'*.txt','DVH text files (*.txt)'; '*.*','All files'}, ...
                'Select DVH TXT File');

            if isequal(file,0)
                app.appendLog("No file selected.");
                return
            end

            txtPath = fullfile(folder, file);

            app.SelectButton.Enable = 'off';
            app.SelectButton.Text = 'PROCESSING...';
            drawnow;

            try
                app.appendLog("------------------------------------------------------------");
                app.appendLog("Selected: " + string(txtPath));

                %% Locate template robustly
                templatePath = app.findTemplate();

                app.appendLog("Template: " + string(templatePath));

                %% Parse DVH
                parsed = app.parseDVH(txtPath);

                app.FileNameLabel.Text = "File: " + string(file);
                app.PatientLabel.Text = "Patient: " + app.displayOrDash(parsed.Patient);
                app.PatientIDLabel.Text = "Patient ID: " + app.displayOrDash(parsed.PatientID);
                app.PlanLabel.Text = "Plan: " + app.displayOrDash(parsed.Plan);
                app.FractionLabel.Text = "Detected Fraction: Fx" + string(parsed.Fraction);

                app.appendLog("Detected fraction: Fx" + string(parsed.Fraction));
                app.appendLog("Parsed " + string(numel(parsed.ROIs)) + " ROI sections.");

                %% Calculate DVH metrics
                [results, ignored] = app.calculateMetrics(parsed);

                recognized = string(fieldnames(results));
                app.appendLog("Recognized structures: " + strjoin(recognized, ", "));

                if ~isempty(ignored)
                    app.appendLog("Ignored/unmapped ROIs: " + strjoin(ignored, ", "));
                end

                %% Build workbook updates
                updates = app.buildUpdates(parsed, results);

                %% Output workbook
                outputPath = app.makeOutputName(txtPath, parsed);
                outputPath = app.makeUniquePath(outputPath);

                app.appendLog("Creating workbook: " + string(outputPath));

                [ok, msg] = copyfile(templatePath, outputPath, 'f');
                if ~ok
                    error("Unable to copy EQD2 template." + newline + ...
                          "Source: " + string(templatePath) + newline + ...
                          "Destination: " + string(outputPath) + newline + ...
                          "System message: " + string(msg));
                end

                if ~isfile(outputPath)
                    error("Workbook copy reported success, but output file was not created:" + newline + ...
                          string(outputPath));
                end

                %% Populate workbook
                updatedSheets = app.populateWorkbook(outputPath, updates);

                app.appendLog("Updated worksheets: " + strjoin(updatedSheets, ", "));
                app.appendLog("SUCCESS");
                app.appendLog("Saved workbook: " + string(outputPath));

                app.SelectButton.Text = 'SELECT ANOTHER DVH TXT FILE...';
                app.SelectButton.Enable = 'on';

                uialert(app.UIFigure, ...
                    sprintf(['EQD2 workbook created successfully.\n\n' ...
                             'Fraction: Fx%d\n\n' ...
                             'Saved to:\n%s'], ...
                             parsed.Fraction, outputPath), ...
                    'EMBRACE-2 Complete', ...
                    'Icon','success');

            catch ME
                app.SelectButton.Text = 'SELECT DVH TXT FILE...';
                app.SelectButton.Enable = 'on';

                report = getReport(ME, 'extended', 'hyperlinks', 'off');
                app.appendLog("ERROR:");
                app.appendLog(string(report));

                uialert(app.UIFigure, ...
                    ME.message, ...
                    'EMBRACE-2 Error', ...
                    'Icon','error');
            end
        end


        function templatePath = findTemplate(app)
            templateName = 'EQD2_with_tolerances_090126.xlsx';

            candidates = strings(0,1);

            %% 1) MATLAB path
            p = which(templateName);
            if ~isempty(p)
                candidates(end+1) = string(p);
            end

            %% 2) Same folder as class file
            classPath = which(class(app));
            if ~isempty(classPath)
                appFolder = fileparts(classPath);
                candidates(end+1) = string(fullfile(appFolder, templateName));
            end

            %% 3) Current MATLAB folder
            candidates(end+1) = string(fullfile(pwd, templateName));

            candidates = unique(candidates, 'stable');

            for i = 1:numel(candidates)
                if isfile(candidates(i))
                    [status, attr] = fileattrib(char(candidates(i)));
                    if status
                        templatePath = char(attr.Name);
                    else
                        templatePath = char(candidates(i));
                    end
                    return
                end
            end

            searched = strjoin(candidates, newline);

            error("Could not find " + templateName + "." + newline + newline + ...
                  "Keep it in the same folder as EMBRACE2_EQD2_Excel_Autogenerator.m " + ...
                  "or add its folder to the MATLAB path." + newline + newline + ...
                  "Locations checked:" + newline + searched);
        end


        function parsed = parseDVH(app, path)

            if ~isfile(path)
                error("The selected DVH TXT file does not exist:" + newline + string(path));
            end

            txt = fileread(path);

            %% Dose units
            if ~isempty(regexpi(txt, 'Absolute Dose\s*-\s*\[cGy\]', 'once'))
                doseUnit = "cGy";
                doseScale = 0.01;

            elseif ~isempty(regexpi(txt, 'Absolute Dose\s*-\s*\[Gy\]', 'once'))
                doseUnit = "Gy";
                doseScale = 1.0;

            else
                error(['Could not identify the DVH dose units.' newline ...
                       'Expected "Absolute Dose - [cGy]" or "Absolute Dose - [Gy]".']);
            end

            %% Cumulative mode
            if isempty(regexpi(txt, 'Cumulative mode', 'once'))
                error("This application expects a cumulative DVH export.");
            end

            %% Header
            parsed.Patient   = string(app.getHeaderValue(txt, 'Patient'));
            parsed.PatientID = string(app.getHeaderValue(txt, 'Patient Id'));
            parsed.Case      = string(app.getHeaderValue(txt, 'Case'));
            parsed.Plan      = string(app.getHeaderValue(txt, 'Plan'));
            parsed.DoseUnit  = doseUnit;

            %% ROI blocks
            [tokens, starts, ends] = regexp( ...
                txt, ...
                '(?m)^\s*ROI:\s*(.+?)\s*$', ...
                'tokens', 'start', 'end');

            if isempty(tokens)
                error("No ROI sections were found in the DVH TXT file.");
            end

            rois = struct('Name',{}, 'DoseGy',{}, 'VolumeCC',{});
            fxDetected = [];

            for i = 1:numel(tokens)

                roiName = strtrim(tokens{i}{1});

                bodyStart = ends(i) + 1;
                if i < numel(tokens)
                    bodyEnd = starts(i+1) - 1;
                else
                    bodyEnd = numel(txt);
                end

                body = txt(bodyStart:bodyEnd);

                %% Fraction detection from ROI name
                fxTok = regexpi( ...
                    roiName, ...
                    '[ _-]*fx([1-6])\s*$', ...
                    'tokens', 'once');

                if ~isempty(fxTok)
                    fxDetected(end+1) = str2double(fxTok{1}); %#ok<AGROW>
                end

                %% Parse numeric rows:
                % bin  dose  cumulative-volume
                rowTok = regexp( ...
                    body, ...
                    ['(?m)^\s*\d+\s+' ...
                     '([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+' ...
                     '([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s*$'], ...
                    'tokens');

                if isempty(rowTok)
                    continue
                end

                dose = zeros(numel(rowTok),1);
                vol  = zeros(numel(rowTok),1);

                for j = 1:numel(rowTok)
                    dose(j) = str2double(rowTok{j}{1}) * doseScale;
                    vol(j)  = str2double(rowTok{j}{2});
                end

                valid = isfinite(dose) & isfinite(vol);
                dose = dose(valid);
                vol  = vol(valid);

                if isempty(dose)
                    continue
                end

                rois(end+1).Name = string(roiName); %#ok<AGROW>
                rois(end).DoseGy = dose;
                rois(end).VolumeCC = vol;
            end

            if isempty(rois)
                error("ROI headers were found, but no numeric DVH data rows could be parsed.");
            end

            %% Fraction fallback from Plan
            fxDetected = unique(fxDetected);

            if isempty(fxDetected)
                pTok = regexpi(char(parsed.Plan), 'fx\s*([1-6])', 'tokens', 'once');
                if ~isempty(pTok)
                    fxDetected = str2double(pTok{1});
                end
            end

            if numel(fxDetected) ~= 1
                error("Could not uniquely determine the fraction number. Detected: " + ...
                      mat2str(fxDetected));
            end

            parsed.Fraction = fxDetected;
            parsed.ROIs = rois;
        end


        function value = getHeaderValue(app, txt, key) %#ok<INUSD>
            pat = ['(?m)^\s*' regexptranslate('escape', key) ':\s*(.*?)\s*$'];
            t = regexp(txt, pat, 'tokens', 'once');

            if isempty(t)
                value = '';
            else
                value = strtrim(t{1});
            end
        end


        function [results, ignored] = calculateMetrics(app, parsed)

            results = struct();
            ignored = strings(0,1);

            for i = 1:numel(parsed.ROIs)

                roi = parsed.ROIs(i);
                key = app.structureKey(roi.Name);

                if key == ""
                    ignored(end+1) = roi.Name; %#ok<AGROW>
                    continue
                end

                %% Total structure volume
                totalCC = max(roi.VolumeCC);

                r = struct();
                r.ROIName = roi.Name;
                r.VolumeCC = totalCC;
                r.Metrics = struct();

                switch key
                    case "gtvres"
                        r.Metrics.D98 = app.doseAtVolume( ...
                            roi.DoseGy, roi.VolumeCC, totalCC*0.98);

                    case "ctv_hr"
                        r.Metrics.D98 = app.doseAtVolume( ...
                            roi.DoseGy, roi.VolumeCC, totalCC*0.98);
                        r.Metrics.D90 = app.doseAtVolume( ...
                            roi.DoseGy, roi.VolumeCC, totalCC*0.90);
                        r.Metrics.D50 = app.doseAtVolume( ...
                            roi.DoseGy, roi.VolumeCC, totalCC*0.50);

                    case "ctv_ir"
                        r.Metrics.D98 = app.doseAtVolume( ...
                            roi.DoseGy, roi.VolumeCC, totalCC*0.98);
                        r.Metrics.D90 = app.doseAtVolume( ...
                            roi.DoseGy, roi.VolumeCC, totalCC*0.90);

                    otherwise
                        r.Metrics.D0p1cc = app.doseAtVolume( ...
                            roi.DoseGy, roi.VolumeCC, 0.1);
                        r.Metrics.D2cc = app.doseAtVolume( ...
                            roi.DoseGy, roi.VolumeCC, 2.0);
                end

                results.(char(key)) = r;
            end

            if isempty(fieldnames(results))
                names = strings(1,numel(parsed.ROIs));
                for i = 1:numel(parsed.ROIs)
                    names(i) = parsed.ROIs(i).Name;
                end

                error("No recognized EMBRACE-2 structures were found." + newline + newline + ...
                      "ROI names parsed from file:" + newline + ...
                      strjoin(names, newline));
            end
        end


        function key = structureKey(app, roiName) %#ok<INUSD>
            % Forgiving matcher for common structure-name variants.

            n = lower(strtrim(string(roiName)));

            % Remove terminal fraction notation:
            % _fx1, -fx1, " fx1", etc.
            n = regexprep(n, '[ _-]*fx[1-6]\s*$', '');

            % Normalize punctuation/spaces.
            n = regexprep(n, '[^a-z0-9]+', '_');
            n = strip(n, '_');

            % Compact representation ignores separators.
            compact = erase(n, '_');

            if contains(compact, "gtvres")
                key = "gtvres";

            elseif contains(compact, "ctvhr")
                key = "ctv_hr";

            elseif contains(compact, "ctvir")
                key = "ctv_ir";

            elseif contains(compact, "bladder")
                key = "bladder";

            elseif contains(compact, "rectum")
                key = "rectum";

            elseif contains(compact, "sigmoid")
                key = "sigmoid";

            elseif contains(compact, "bowel") || contains(compact, "intestin")
                key = "bowel";

            else
                key = "";
            end
        end


        function d = doseAtVolume(app, doseGy, volCC, targetCC) %#ok<INUSD>
            % Interpolate cumulative DVH dose at a requested absolute volume.

            doseGy = doseGy(:);
            volCC  = volCC(:);

            valid = isfinite(doseGy) & isfinite(volCC);
            doseGy = doseGy(valid);
            volCC  = volCC(valid);

            if isempty(doseGy)
                d = NaN;
                return
            end

            [doseGy, idx] = sort(doseGy, 'ascend');
            volCC = volCC(idx);

            %% Remove duplicate dose points by keeping minimum cumulative volume
            [uniqueDose, ~, grp] = unique(doseGy, 'stable');

            if numel(uniqueDose) ~= numel(doseGy)
                newVol = zeros(size(uniqueDose));
                for k = 1:numel(uniqueDose)
                    newVol(k) = min(volCC(grp == k));
                end
                doseGy = uniqueDose;
                volCC = newVol;
            end

            %% Search for crossing
            for i = 1:numel(doseGy)-1
                v1 = volCC(i);
                v2 = volCC(i+1);

                if (v1 >= targetCC && targetCC >= v2) || ...
                   (v1 <= targetCC && targetCC <= v2)

                    d1 = doseGy(i);
                    d2 = doseGy(i+1);

                    if abs(v2-v1) < eps
                        d = d1;
                    else
                        f = (targetCC-v1)/(v2-v1);
                        d = d1 + f*(d2-d1);
                    end
                    return
                end
            end

            %% Edge handling
            [~, nearestIdx] = min(abs(volCC-targetCC));
            d = doseGy(nearestIdx);
        end


        function updates = buildUpdates(app, parsed, results) %#ok<INUSD>

            cols = {'C','D','E','F','G','H'};
            col = cols{parsed.Fraction};

            map = struct();

            map.gtvres.volume = 38;
            map.gtvres.D98 = 39;

            map.ctv_hr.volume = 42;
            map.ctv_hr.D98 = 43;
            map.ctv_hr.D90 = 45;
            map.ctv_hr.D50 = 47;

            map.ctv_ir.volume = 50;
            map.ctv_ir.D98 = 51;
            map.ctv_ir.D90 = 53;

            map.bladder.volume = 56;
            map.bladder.D0p1cc = 59;
            map.bladder.D2cc = 61;

            map.rectum.volume = 64;
            map.rectum.D0p1cc = 67;
            map.rectum.D2cc = 69;

            map.sigmoid.volume = 72;
            map.sigmoid.D0p1cc = 73;
            map.sigmoid.D2cc = 75;

            map.bowel.volume = 78;
            map.bowel.D0p1cc = 79;
            map.bowel.D2cc = 81;

            updates = struct();

            structures = fieldnames(results);

            for i = 1:numel(structures)

                k = structures{i};

                if ~isfield(map, k)
                    continue
                end

                %% Structure volume
                volumeCell = [col num2str(map.(k).volume)];
                updates.(volumeCell) = results.(k).VolumeCC;

                %% Dose metrics
                metrics = fieldnames(results.(k).Metrics);

                for j = 1:numel(metrics)
                    metricName = metrics{j};

                    if isfield(map.(k), metricName)
                        value = results.(k).Metrics.(metricName);

                        if isfinite(value)
                            cellRef = [col num2str(map.(k).(metricName))];
                            updates.(cellRef) = value;
                        end
                    end
                end
            end
        end


        function updatedSheets = populateWorkbook(app, outputPath, updates)

            if ~isfile(outputPath)
                error("Output workbook does not exist:" + newline + string(outputPath));
            end

            %% Canonical full path
            [status, attr] = fileattrib(outputPath);
            if status
                outputPath = attr.Name;
            end

            %% Identify relevant sheets using MATLAB
            allSheets = string(sheetnames(outputPath));
            targetSheets = allSheets(contains(upper(allSheets), "FX1-4"));

            if isempty(targetSheets)
                error('No worksheet containing "FX1-4" was found in the EQD2 template.');
            end

            refs = fieldnames(updates);

            %% Preferred Windows path: one Excel session for entire workbook
            if ispc
                excel = [];
                wb = [];

                try
                    excel = actxserver('Excel.Application');
                    excel.Visible = false;
                    excel.DisplayAlerts = false;

                    wb = excel.Workbooks.Open(char(outputPath));

                    for s = 1:numel(targetSheets)
                        ws = wb.Worksheets.Item(char(targetSheets(s)));

                        for i = 1:numel(refs)
                            ws.Range(refs{i}).Value = updates.(refs{i});
                        end
                    end

                    %% Force all EQD2 formulas to update
                    excel.CalculateFullRebuild;

                    wb.Save;
                    wb.Close(false);
                    excel.Quit;
                    delete(excel);

                    updatedSheets = targetSheets;
                    return

                catch ME
                    %% Clean up COM objects
                    try
                        if ~isempty(wb)
                            wb.Close(false);
                        end
                    catch
                    end

                    try
                        if ~isempty(excel)
                            excel.Quit;
                            delete(excel);
                        end
                    catch
                    end

                    app.appendLog("Excel automation failed; using MATLAB fallback.");
                    app.appendLog("Excel message: " + string(ME.message));
                end
            end

            %% MATLAB fallback
            for s = 1:numel(targetSheets)
                for i = 1:numel(refs)
                    writematrix( ...
                        updates.(refs{i}), ...
                        outputPath, ...
                        'Sheet', char(targetSheets(s)), ...
                        'Range', refs{i});
                end
            end

            updatedSheets = targetSheets;
        end


        function out = makeOutputName(app, txtPath, parsed) %#ok<INUSD>
            % Save the completed workbook using the same base filename
            % as the selected TXT file.
            %
            % Example:
            %   DVH_absolute_v2.txt  ->  DVH_absolute_v2.xlsx

            [folder, baseName, ~] = fileparts(txtPath);

            % If the selected TXT folder is not writable,
            % fall back to the MATLAB Current Folder.
            testFile = fullfile(folder, ...
                ['.__eqd2_write_test_' char(java.util.UUID.randomUUID) '.tmp']);

            canWrite = false;

            try
                fid = fopen(testFile, 'w');

                if fid > 0
                    fclose(fid);
                    delete(testFile);
                    canWrite = true;
                end
            catch
            end

            if ~canWrite
                folder = pwd;
            end

            out = fullfile(folder, [baseName '.xlsx']);
        end


                function out = makeUniquePath(app, out) %#ok<INUSD>
            if ~isfile(out)
                return
            end

            [folder, name, ext] = fileparts(out);

            k = 2;
            while true
                candidate = fullfile(folder, sprintf('%s_%d%s', name, k, ext));

                if ~isfile(candidate)
                    out = candidate;
                    return
                end

                k = k + 1;
            end
        end


        function appendLog(app, message)
            message = string(message);

            if isempty(app.DetailsArea.Value)
                current = strings(0,1);
            else
                current = string(app.DetailsArea.Value);
            end

            newLines = splitlines(message);
            current = [current; newLines];

            app.DetailsArea.Value = cellstr(current);
            drawnow;
        end


        function clearLog(app, ~)
            app.DetailsArea.Value = {};
            app.appendLog("Ready. Select a DVH TXT file to begin.");
        end


        function out = displayOrDash(app, value) %#ok<INUSD>
            value = string(value);

            if strlength(strtrim(value)) == 0
                out = "—";
            else
                out = value;
            end
        end


        function createComponents(app)

            %% Main window
            app.UIFigure = uifigure('Visible','off');
            app.UIFigure.Position = [100 75 900 760];
            app.UIFigure.Name = 'EMBRACE-2 EQD2 Excel Autogenerator';
            app.UIFigure.Color = app.UFDarkBlue;

            app.MainGrid = uigridlayout(app.UIFigure, [7 1]);
            app.MainGrid.RowHeight = {95, 78, 90, 160, '1x', 105, 42};
            app.MainGrid.RowSpacing = 10;
            app.MainGrid.Padding = [0 0 0 0];

            %% Header
            app.HeaderPanel = uipanel(app.MainGrid);
            app.HeaderPanel.BackgroundColor = app.UFDarkBlue;
            app.HeaderPanel.BorderType = 'none';

            app.HeaderGrid = uigridlayout(app.HeaderPanel, [1 3]);
            app.HeaderGrid.ColumnWidth = {90, '1x', 250};
            app.HeaderGrid.Padding = [24 10 24 10];
            app.HeaderGrid.ColumnSpacing = 12;

            app.UFLabel = uilabel(app.HeaderGrid);
            app.UFLabel.Text = 'UF';
            app.UFLabel.FontSize = 34;
            app.UFLabel.FontWeight = 'bold';
            app.UFLabel.FontColor = [1 1 1];
            app.UFLabel.HorizontalAlignment = 'center';

            app.InstituteLabel = uilabel(app.HeaderGrid);
            app.InstituteLabel.Text = sprintf('UF PROTON INSTITUTE\nDepartment of Radiation Oncology');
            app.InstituteLabel.FontSize = 18;
            app.InstituteLabel.FontWeight = 'bold';
            app.InstituteLabel.FontColor = [1 1 1];

            app.HeaderTagline = uilabel(app.HeaderGrid);
            app.HeaderTagline.Text = sprintf('PEOPLE   |   PURPOSE   |   PROTONS\nHEAL TODAY. BRIGHTER TOMORROWS.');
            app.HeaderTagline.FontSize = 11;
            app.HeaderTagline.FontColor = [1 1 1];
            app.HeaderTagline.HorizontalAlignment = 'right';

            %% Title
            titlePanel = uipanel(app.MainGrid);
            titlePanel.BorderType = 'none';
            titlePanel.BackgroundColor = app.UFDarkBlue;

            titleGrid = uigridlayout(titlePanel, [2 1]);
            titleGrid.RowHeight = {44, 24};
            titleGrid.Padding = [20 4 20 4];
            titleGrid.RowSpacing = 0;

            app.TitleLabel = uilabel(titleGrid);
            app.TitleLabel.Text = 'EMBRACE-2 EQD2 Excel Autogenerator';
            app.TitleLabel.FontSize = 25;
            app.TitleLabel.FontWeight = 'bold';
            app.TitleLabel.FontColor = [1 1 1];
            app.TitleLabel.HorizontalAlignment = 'center';

            app.SubtitleLabel = uilabel(titleGrid);
            app.SubtitleLabel.Text = ...
                'Select a DVH TXT file and automatically generate the populated EQD2 workbook.';
            app.SubtitleLabel.FontSize = 13;
            app.SubtitleLabel.FontColor = [1 1 1];
            app.SubtitleLabel.HorizontalAlignment = 'center';

            %% Workflow
            app.WorkflowPanel = uipanel(app.MainGrid);
            app.WorkflowPanel.BackgroundColor = [0.035 0.245 0.50];
            app.WorkflowPanel.BorderColor = [0.35 0.60 0.85];

            app.WorkflowGrid = uigridlayout(app.WorkflowPanel, [1 5]);
            app.WorkflowGrid.ColumnWidth = {'1x',50,'1x',50,'1x'};
            app.WorkflowGrid.Padding = [22 14 22 14];

            app.Step1Label = uilabel(app.WorkflowGrid);
            app.Step1Label.Text = sprintf('1  SELECT DVH\nTXT FILE');
            app.Step1Label.FontSize = 14;
            app.Step1Label.FontWeight = 'bold';
            app.Step1Label.FontColor = [1 1 1];
            app.Step1Label.HorizontalAlignment = 'center';

            app.Arrow1Label = uilabel(app.WorkflowGrid);
            app.Arrow1Label.Text = '→';
            app.Arrow1Label.FontSize = 28;
            app.Arrow1Label.FontWeight = 'bold';
            app.Arrow1Label.FontColor = app.UFOrange;
            app.Arrow1Label.HorizontalAlignment = 'center';

            app.Step2Label = uilabel(app.WorkflowGrid);
            app.Step2Label.Text = sprintf('2  CALCULATE\nDVH METRICS');
            app.Step2Label.FontSize = 14;
            app.Step2Label.FontWeight = 'bold';
            app.Step2Label.FontColor = [1 1 1];
            app.Step2Label.HorizontalAlignment = 'center';

            app.Arrow2Label = uilabel(app.WorkflowGrid);
            app.Arrow2Label.Text = '→';
            app.Arrow2Label.FontSize = 28;
            app.Arrow2Label.FontWeight = 'bold';
            app.Arrow2Label.FontColor = app.UFOrange;
            app.Arrow2Label.HorizontalAlignment = 'center';

            app.Step3Label = uilabel(app.WorkflowGrid);
            app.Step3Label.Text = sprintf('3  GENERATE\nEQD2 EXCEL FILE');
            app.Step3Label.FontSize = 14;
            app.Step3Label.FontWeight = 'bold';
            app.Step3Label.FontColor = [1 1 1];
            app.Step3Label.HorizontalAlignment = 'center';

            %% Input panel
            app.InputPanel = uipanel(app.MainGrid);
            app.InputPanel.BackgroundColor = [0.035 0.245 0.50];
            app.InputPanel.BorderColor = [0.35 0.60 0.85];

            app.InputGrid = uigridlayout(app.InputPanel, [1 2]);
            app.InputGrid.ColumnWidth = {'1.05x','0.95x'};
            app.InputGrid.Padding = [18 18 18 18];
            app.InputGrid.ColumnSpacing = 24;

            app.SelectButton = uibutton(app.InputGrid, 'push');
            app.SelectButton.Text = 'SELECT DVH TXT FILE...';
            app.SelectButton.FontSize = 18;
            app.SelectButton.FontWeight = 'bold';
            app.SelectButton.FontColor = [1 1 1];
            app.SelectButton.BackgroundColor = app.UFOrange;
            app.SelectButton.ButtonPushedFcn = @(s,e)app.selectAndProcess(e);

            app.FileInfoGrid = uigridlayout(app.InputGrid, [5 1]);
            app.FileInfoGrid.RowHeight = {'1x','1x','1x','1x','1x'};
            app.FileInfoGrid.Padding = [4 2 4 2];
            app.FileInfoGrid.RowSpacing = 3;

            app.FileNameLabel = uilabel(app.FileInfoGrid);
            app.FileNameLabel.Text = 'File: —';
            app.FileNameLabel.FontSize = 12;
            app.FileNameLabel.FontColor = [1 1 1];

            app.PatientLabel = uilabel(app.FileInfoGrid);
            app.PatientLabel.Text = 'Patient: —';
            app.PatientLabel.FontSize = 12;
            app.PatientLabel.FontColor = [1 1 1];

            app.PatientIDLabel = uilabel(app.FileInfoGrid);
            app.PatientIDLabel.Text = 'Patient ID: —';
            app.PatientIDLabel.FontSize = 12;
            app.PatientIDLabel.FontColor = [1 1 1];

            app.PlanLabel = uilabel(app.FileInfoGrid);
            app.PlanLabel.Text = 'Plan: —';
            app.PlanLabel.FontSize = 12;
            app.PlanLabel.FontColor = [1 1 1];

            app.FractionLabel = uilabel(app.FileInfoGrid);
            app.FractionLabel.Text = 'Detected Fraction: —';
            app.FractionLabel.FontSize = 12;
            app.FractionLabel.FontWeight = 'bold';
            app.FractionLabel.FontColor = [1 1 1];

            %% Log
            app.LogPanel = uipanel(app.MainGrid);
            app.LogPanel.BackgroundColor = [0.035 0.245 0.50];
            app.LogPanel.BorderColor = [0.35 0.60 0.85];

            app.LogGrid = uigridlayout(app.LogPanel, [2 2]);
            app.LogGrid.RowHeight = {32,'1x'};
            app.LogGrid.ColumnWidth = {'1x',110};
            app.LogGrid.Padding = [16 10 16 14];

            app.LogHeaderLabel = uilabel(app.LogGrid);
            app.LogHeaderLabel.Text = 'Processing Log';
            app.LogHeaderLabel.FontSize = 15;
            app.LogHeaderLabel.FontWeight = 'bold';
            app.LogHeaderLabel.FontColor = [1 1 1];

            app.ClearLogButton = uibutton(app.LogGrid, 'push');
            app.ClearLogButton.Text = 'Clear Log';
            app.ClearLogButton.ButtonPushedFcn = @(s,e)app.clearLog(e);

            app.DetailsArea = uitextarea(app.LogGrid);
            app.DetailsArea.Layout.Row = 2;
            app.DetailsArea.Layout.Column = [1 2];
            app.DetailsArea.Editable = 'off';
            app.DetailsArea.FontName = 'Consolas';
            app.DetailsArea.FontSize = 11;
            app.DetailsArea.BackgroundColor = [0.995 0.995 0.995];

            %% Notes
            app.NotesPanel = uipanel(app.MainGrid);
            app.NotesPanel.BackgroundColor = [0.035 0.245 0.50];
            app.NotesPanel.BorderColor = [0.35 0.60 0.85];

            app.NotesGrid = uigridlayout(app.NotesPanel, [2 1]);
            app.NotesGrid.RowHeight = {26,'1x'};
            app.NotesGrid.Padding = [18 10 18 10];
            app.NotesGrid.RowSpacing = 3;

            app.NotesTitle = uilabel(app.NotesGrid);
            app.NotesTitle.Text = 'Notes';
            app.NotesTitle.FontSize = 15;
            app.NotesTitle.FontWeight = 'bold';
            app.NotesTitle.FontColor = [1 1 1];

            app.NotesLabel = uilabel(app.NotesGrid);
            app.NotesLabel.Text = sprintf([ ...
                '• Keep EQD2_with_tolerances_090126.xlsx with this app or on the MATLAB path.\n' ...
                '• The app detects Fx1-Fx6, converts cGy to Gy when needed, and populates all FX1-4 sheets.\n' ...
                '• The Excel file uses the same base name as the selected TXT file and is saved beside it when writable.\n' ...
                '• Validate generated metrics/workbook against the clinical workflow before clinical use.']);
            app.NotesLabel.FontSize = 11;
            app.NotesLabel.FontColor = [1 1 1];

            %% Footer
            app.FooterPanel = uipanel(app.MainGrid);
            app.FooterPanel.BackgroundColor = app.UFDarkBlue;
            app.FooterPanel.BorderType = 'none';

            app.FooterGrid = uigridlayout(app.FooterPanel, [1 2]);
            app.FooterGrid.ColumnWidth = {'1x','1x'};
            app.FooterGrid.Padding = [20 4 20 4];

            app.FooterLeft = uilabel(app.FooterGrid);
            app.FooterLeft.Text = 'UF Proton Institute  |  Radiation Oncology';
            app.FooterLeft.FontColor = [1 1 1];
            app.FooterLeft.FontSize = 10;

            app.FooterRight = uilabel(app.FooterGrid);
            app.FooterRight.Text = 'EMBRACE-2  |  EQD2 AUTOMATION';
            app.FooterRight.FontColor = [1 1 1];
            app.FooterRight.FontSize = 10;
            app.FooterRight.HorizontalAlignment = 'right';

            app.UIFigure.Visible = 'on';
        end
    end


    methods (Access = public)

        function app = EMBRACE2_EQD2_Excel_Autogenerator
            createComponents(app);
            registerApp(app, app.UIFigure);
            runStartupFcn(app, @startupFcn);

            if nargout == 0
                clear app
            end
        end


        function delete(app)
            if ~isempty(app.UIFigure) && isvalid(app.UIFigure)
                delete(app.UIFigure);
            end
        end
    end
end
