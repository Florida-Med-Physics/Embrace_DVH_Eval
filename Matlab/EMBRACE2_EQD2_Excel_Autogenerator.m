classdef EMBRACE2_EQD2_Excel_Autogenerator < matlab.apps.AppBase
    % EMBRACE2_EQD2_Excel_Autogenerator
    %
    % Excel-like EMBRACE-2 dashboard
    % MATLAB R2024b
    %
    % Layout:
    %   TARGETS:
    %   F1 | F2 | F3 | F4 | TOTAL BT + EBT | Planning Goal | Tolerance
    %
    %   OARs:
    %   F1 | F2 | F3 | F4 | TOTAL BT + EBT | Soft Constraints | Hard Constraints
    %
    % DVH loading:
    %   Load Fx1 -> populates Fx1 and carries forward to Fx2-Fx4
    %   Load Fx2 -> overwrites Fx2 and carries forward to Fx3-Fx4
    %   Load Fx3 -> overwrites Fx3 and carries forward to Fx4
    %   Load Fx4 -> overwrites Fx4 only
    %
    % Display:
    %   All calculated values shown to 2 decimal places.
    %
    % Total cell color:
    %   Green  = meets Planning Goal / Soft Constraint
    %   Yellow = misses Planning Goal / Soft Constraint,
    %            but meets Tolerance / Hard Constraint
    %   Red    = fails Tolerance / Hard Constraint
    %
    % Required template:
    %   EQD2_with_tolerances_090126.xlsx

    properties (Access = public)
        UIFigure matlab.ui.Figure
        MainGrid matlab.ui.container.GridLayout

        HeaderPanel matlab.ui.container.Panel
        HeaderGrid matlab.ui.container.GridLayout
        TitleLabel matlab.ui.control.Label
        BrandLabel matlab.ui.control.Label

        LoadPanel matlab.ui.container.Panel
        LoadGrid matlab.ui.container.GridLayout
        LoadLabel matlab.ui.control.Label
        Fx1Button matlab.ui.control.Button
        Fx2Button matlab.ui.control.Button
        Fx3Button matlab.ui.control.Button
        Fx4Button matlab.ui.control.Button
        PlanStatusLabel matlab.ui.control.Label
        FileStatusLabel matlab.ui.control.Label

        PriorRTHeader matlab.ui.control.Label
        PriorRTTable matlab.ui.control.Table

        TargetHeader matlab.ui.control.Label
        TargetTable matlab.ui.control.Table

        OARHeader matlab.ui.control.Label
        OARTable matlab.ui.control.Table

        FooterPanel matlab.ui.container.Panel
        FooterGrid matlab.ui.container.GridLayout
        StatusLabel matlab.ui.control.Label
        ClearButton matlab.ui.control.Button
        ExportButton matlab.ui.control.Button
    end

    properties (Access = private)
        Black = [0 0 0]
        NearBlack = [0.025 0.025 0.030]
        TableBlack = [0.055 0.055 0.065]
        TableBlackAlt = [0.085 0.085 0.095]
        SectionGray = [0.12 0.12 0.14]

        UFBlue = [0.000 0.129 0.412]
        UFOrange = [0.980 0.290 0.000]
        White = [1 1 1]
        Muted = [0.72 0.76 0.82]

        % Excel-like worksheet palette
        CurrentDoseBlue = [0.78 0.93 0.95]
        EQDWhite = [1.00 1.00 1.00]
        HeaderBlue = [0.70 0.88 0.91]
        ConstraintWhite = [1.00 1.00 1.00]

        PassGreen = [0.45 0.75 0.43]
        WarnYellow = [0.96 0.80 0.32]
        FailRed = [0.88 0.34 0.30]

        TargetDefs
        OARDefs

        LoadedFiles = strings(1,4)
        ExplicitlyLoaded = false(1,4)
        PlanNames = strings(1,4)

        PatientName = ""
        PatientID = ""
    end

    methods (Access = private)

        function startupFcn(app)
            app.updatePatientLabel();
            app.updatePlanStatus();
            app.refreshFileStatus();
            app.recalculateAll();
            app.StatusLabel.Text = ...
                'Set prior RT fractionation, then load Fx1-Fx4 DVHs or manually edit physical values.';
        end


        function initializeDefinitions(app)

            % Columns:
            % 1 display label (units embedded in brackets)
            % 2 type: spacer / section / physical / eqd
            % 3 internal key
            % 4 physical source key for EQD2 rows
            % 5 Excel row
            % 6 alpha/beta
            % 7 legacy template EBRT EQD2 baseline
            % 8 goal/soft constraint text
            % 9 tolerance/hard constraint text
            %
            % ROI volumes are shown as their own physical rows so each
            % brachytherapy fraction can have an independent contour volume.

            app.TargetDefs = {
                '',                  'spacer',   '',                    '',               NaN, NaN, NaN, '',      ''
                'GTV_res',           'section',  '',                    '',               NaN, NaN, NaN, '',      ''
                'Volume [cc]',       'physical', 'gtvres_volume',       '',                38, NaN, NaN, '',      ''
                'D98 [Gy]',          'physical', 'gtvres_D98',          '',                39, NaN, NaN, '',      ''
                'D98 EQD210 [Gy]',   'eqd',      'gtvres_D98_EQD210',   'gtvres_D98',     NaN, 10, 44.25, '>95',   '>90'

                '',                  'spacer',   '',                    '',               NaN, NaN, NaN, '',      ''
                'CTV_HR',            'section',  '',                    '',               NaN, NaN, NaN, '',      ''
                'Volume [cc]',       'physical', 'ctvhr_volume',        '',                42, NaN, NaN, '',      ''
                'D98 [Gy]',          'physical', 'ctvhr_D98',           '',                43, NaN, NaN, '',      ''
                'D98 EQD210 [Gy]',   'eqd',      'ctvhr_D98_EQD210',    'ctvhr_D98',      NaN, 10, 44.25, '>75',   '>75'
                'D90 [Gy]',          'physical', 'ctvhr_D90',           '',                45, NaN, NaN, '',      ''
                'D90 EQD210 [Gy]',   'eqd',      'ctvhr_D90_EQD210',    'ctvhr_D90',      NaN, 10, 44.25, '90-95', '>85'
                'D50 [Gy]',          'physical', 'ctvhr_D50',           '',                47, NaN, NaN, '',      ''
                'D50 EQD210 [Gy]',   'eqd',      'ctvhr_D50_EQD210',    'ctvhr_D50',      NaN, 10, 44.25, '',      ''

                '',                  'spacer',   '',                    '',               NaN, NaN, NaN, '',      ''
                'CTV_IR',            'section',  '',                    '',               NaN, NaN, NaN, '',      ''
                'Volume [cc]',       'physical', 'ctvir_volume',        '',                50, NaN, NaN, '',      ''
                'D98 [Gy]',          'physical', 'ctvir_D98',           '',                51, NaN, NaN, '',      ''
                'D98 EQD210 [Gy]',   'eqd',      'ctvir_D98_EQD210',    'ctvir_D98',      NaN, 10, 44.25, '>60',   '>60'
                'D90 [Gy]',          'physical', 'ctvir_D90',           '',                53, NaN, NaN, '',      ''
                'D90 EQD210 [Gy]',   'eqd',      'ctvir_D90_EQD210',    'ctvir_D90',      NaN, 10, 44.25, '',      ''
                };

            app.OARDefs = {
                '',                         'spacer',   '',                    '',               NaN, NaN, NaN, '',    ''
                'BLADDER',                  'section',  '',                    '',               NaN, NaN, NaN, '',    ''
                'Volume [cc]',              'physical', 'bladder_volume',      '',                56, NaN, NaN, '',    ''
                'D0.1cc [Gy]',              'physical', 'bladder_D0p1',        '',                59, NaN, NaN, '',    ''
                'D0.1cc EQD23 [Gy]',        'eqd',      'bladder_D0p1_EQD23',  'bladder_D0p1',   NaN, 3, 43.20, '',    ''
                'D2cc [Gy]',                'physical', 'bladder_D2',          '',                61, NaN, NaN, '',    ''
                'D2cc EQD23 [Gy]',          'eqd',      'bladder_D2_EQD23',    'bladder_D2',     NaN, 3, 43.20, '<80', '<90'

                '',                         'spacer',   '',                    '',               NaN, NaN, NaN, '',    ''
                'RECTUM',                   'section',  '',                    '',               NaN, NaN, NaN, '',    ''
                'Volume [cc]',              'physical', 'rectum_volume',       '',                64, NaN, NaN, '',    ''
                'D0.1cc [Gy]',              'physical', 'rectum_D0p1',         '',                67, NaN, NaN, '',    ''
                'D0.1cc EQD23 [Gy]',        'eqd',      'rectum_D0p1_EQD23',   'rectum_D0p1',    NaN, 3, 43.20, '',    ''
                'D2cc [Gy]',                'physical', 'rectum_D2',           '',                69, NaN, NaN, '',    ''
                'D2cc EQD23 [Gy]',          'eqd',      'rectum_D2_EQD23',     'rectum_D2',      NaN, 3, 43.20, '<65', '<75'

                '',                         'spacer',   '',                    '',               NaN, NaN, NaN, '',    ''
                'SIGMOID',                  'section',  '',                    '',               NaN, NaN, NaN, '',    ''
                'Volume [cc]',              'physical', 'sigmoid_volume',      '',                72, NaN, NaN, '',    ''
                'D0.1cc [Gy]',              'physical', 'sigmoid_D0p1',        '',                73, NaN, NaN, '',    ''
                'D0.1cc EQD23 [Gy]',        'eqd',      'sigmoid_D0p1_EQD23',  'sigmoid_D0p1',   NaN, 3, 43.20, '',    ''
                'D2cc [Gy]',                'physical', 'sigmoid_D2',          '',                75, NaN, NaN, '',    ''
                'D2cc EQD23 [Gy]',          'eqd',      'sigmoid_D2_EQD23',    'sigmoid_D2',     NaN, 3, 43.20, '<70', '<75'

                '',                         'spacer',   '',                    '',               NaN, NaN, NaN, '',    ''
                'INTESTINES OR BOWEL',      'section',  '',                    '',               NaN, NaN, NaN, '',    ''
                'Volume [cc]',              'physical', 'bowel_volume',        '',                78, NaN, NaN, '',    ''
                'D0.1cc [Gy]',              'physical', 'bowel_D0p1',          '',                79, NaN, NaN, '',    ''
                'D0.1cc EQD23 [Gy]',        'eqd',      'bowel_D0p1_EQD23',    'bowel_D0p1',     NaN, 3, 43.20, '',    ''
                'D2cc [Gy]',                'physical', 'bowel_D2',            '',                81, NaN, NaN, '',    ''
                'D2cc EQD23 [Gy]',          'eqd',      'bowel_D2_EQD23',      'bowel_D2',       NaN, 3, 43.20, '<70', '<75'
                };
        end


        function data = makeInitialTable(app,defs)
            n = size(defs,1);
            data = cell(n,8);

            for r = 1:n
                rowType = string(defs{r,2});

                if rowType == "physical" || rowType == "eqd"
                    % Indent dose/constraint rows beneath the ROI title.
                    data{r,1} = ['    ' char(string(defs{r,1}))];
                else
                    data{r,1} = defs{r,1};
                end

                for c = 2:6
                    data{r,c} = '';
                end

                data{r,7} = defs{r,8};
                data{r,8} = defs{r,9};
            end
        end


        function updatePlanStatus(app)
            parts = strings(1,4);

            for fx = 1:4
                plan = app.PlanNames(fx);

                if strlength(plan)==0
                    plan = "—";
                end

                parts(fx) = sprintf('F%d Plan: %s',fx,char(plan));
            end

            app.PlanStatusLabel.Text = strjoin(parts,'    |    ');
        end


        function updatePatientLabel(app)
            patient = app.PatientName;
            patientID = app.PatientID;

            if strlength(patient)==0
                patient = "—";
            end
            if strlength(patientID)==0
                patientID = "—";
            end

            app.LoadLabel.Text = sprintf('Patient: %s    |    Patient ID: %s', ...
                char(patient),char(patientID));
        end


        function acceptPatientMetadata(app,parsed)
            newPatient = strtrim(string(parsed.Patient));
            newID = strtrim(string(parsed.PatientID));

            if strlength(app.PatientName)==0 && strlength(newPatient)>0
                app.PatientName = newPatient;
            elseif strlength(newPatient)>0 && strlength(app.PatientName)>0 && ...
                    ~strcmpi(app.PatientName,newPatient)
                error(sprintf(['Patient mismatch.\n\nLoaded patient: %s\n' ...
                    'Current dashboard patient: %s'],newPatient,app.PatientName));
            end

            if strlength(app.PatientID)==0 && strlength(newID)>0
                app.PatientID = newID;
            elseif strlength(newID)>0 && strlength(app.PatientID)>0 && ...
                    ~strcmpi(app.PatientID,newID)
                error(sprintf(['Patient ID mismatch.\n\nLoaded Patient ID: %s\n' ...
                    'Current dashboard Patient ID: %s'],newID,app.PatientID));
            end

            app.updatePatientLabel();
        end


        function loadFraction(app,fx)

            [file,folder] = uigetfile( ...
                {'*.txt','DVH text files (*.txt)'; '*.*','All files'}, ...
                sprintf('Load Fx%d DVH TXT',fx));

            if isequal(file,0)
                return
            end

            try
                path = fullfile(folder,file);

                app.StatusLabel.Text = sprintf('Reading Fx%d DVH...',fx);
                drawnow;

                parsed = app.parseDVH(path);
                app.acceptPatientMetadata(parsed);
                metrics = app.calculateAllMetrics(parsed);

                % This fraction was explicitly selected by the user.
                % It is now protected from carry-forward from any earlier Fx.
                app.ExplicitlyLoaded(fx) = true;
                app.LoadedFiles(fx) = string(file);
                app.PlanNames(fx) = strtrim(string(parsed.Plan));
                app.updatePlanStatus();

                % Always populate the selected fraction itself.
                app.applyMetrics(app.TargetTable,app.TargetDefs,fx,metrics,false);
                app.applyMetrics(app.OARTable,app.OARDefs,fx,metrics,false);

                % Carry this newly selected fraction only into later fractions
                % that have NEVER been explicitly loaded by the user.
                %
                % Examples:
                %   Load Fx1 -> fills Fx1-Fx4.
                %   Then load Fx2 -> replaces Fx2 and carries Fx2 into Fx3-Fx4.
                %   If Fx3 had already been explicitly loaded, Fx3 is preserved.
                %   Loading/editing an earlier fraction never pushes backward.
                carriedTo = [];

                for destinationFx = fx+1:4
                    if ~app.ExplicitlyLoaded(destinationFx)
                        app.copyMetricsToFraction( ...
                            app.TargetTable,app.TargetDefs,destinationFx,metrics);
                        app.copyMetricsToFraction( ...
                            app.OARTable,app.OARDefs,destinationFx,metrics);

                        app.LoadedFiles(destinationFx) = ...
                            string(file) + sprintf(" (carried from Fx%d)",fx);

                        carriedTo(end+1) = destinationFx; %#ok<AGROW>
                    end
                end

                app.refreshFileStatus();
                app.recalculateAll();

                if isempty(carriedTo)
                    app.StatusLabel.Text = sprintf( ...
                        'Loaded Fx%d: %s. Later explicitly loaded fractions were preserved.', ...
                        fx,file);
                else
                    carriedText = strjoin("Fx" + string(carriedTo),", ");
                    app.StatusLabel.Text = sprintf( ...
                        'Loaded Fx%d: %s. Carried forward to %s; explicitly loaded later fractions were preserved.', ...
                        fx,file,char(carriedText));
                end

            catch ME
                app.StatusLabel.Text = sprintf('Fx%d load failed.',fx);
                uialert(app.UIFigure,ME.message, ...
                    sprintf('Fx%d DVH Import Error',fx), ...
                    'Icon','error');
            end
        end


        function applyMetrics(app,tableHandle,defs,fx,metrics,carryForward)

            if nargin < 6
                carryForward = false;
            end

            % Populate the explicitly selected fraction.
            app.copyMetricsToFraction(tableHandle,defs,fx,metrics);

            % Optional legacy/internal carry behavior. Normal GUI loading now
            % performs protected carry-forward in loadFraction().
            if carryForward
                for destinationFx = fx+1:4
                    if ~app.ExplicitlyLoaded(destinationFx)
                        app.copyMetricsToFraction( ...
                            tableHandle,defs,destinationFx,metrics);
                    end
                end
            end
        end


        function copyMetricsToFraction(app,tableHandle,defs,destinationFx,metrics)

            data = tableHandle.Data;
            names = string(fieldnames(metrics));

            for r = 1:size(defs,1)
                rowType = string(defs{r,2});
                key = string(defs{r,3});

                if rowType ~= "physical" || strlength(key)==0 || ~any(names == key)
                    continue
                end

                value = metrics.(char(key));

                if ~isfinite(value)
                    continue
                end

                data{r,destinationFx+1} = app.fmt(value);
            end

            tableHandle.Data = data;
        end


        function parsed = parseDVH(app,path)

            if ~isfile(path)
                error("TXT file not found:" + newline + string(path));
            end

            txt = fileread(path);

            if ~isempty(regexpi(txt,'Absolute Dose\s*-\s*\[cGy\]','once'))
                doseScale = 0.01;
            elseif ~isempty(regexpi(txt,'Absolute Dose\s*-\s*\[Gy\]','once'))
                doseScale = 1.0;
            else
                error(['Could not identify dose units.' newline ...
                    'Expected "Absolute Dose - [cGy]" or "Absolute Dose - [Gy]".']);
            end

            if isempty(regexpi(txt,'Cumulative mode','once'))
                error('This app expects a cumulative DVH export.');
            end

            parsed.Patient = string(app.getHeaderValue(txt,'Patient'));
            parsed.PatientID = string(app.getHeaderValue(txt,'Patient Id'));
            parsed.Plan = string(app.getHeaderValue(txt,'Plan'));

            [tokens,starts,ends] = regexp( ...
                txt,'(?m)^\s*ROI:\s*(.+?)\s*$', ...
                'tokens','start','end');

            if isempty(tokens)
                error('No ROI sections were found.');
            end

            rois = struct('Name',{},'DoseGy',{},'VolumeCC',{});

            for i = 1:numel(tokens)

                roiName = strtrim(tokens{i}{1});

                bodyStart = ends(i)+1;
                if i < numel(tokens)
                    bodyEnd = starts(i+1)-1;
                else
                    bodyEnd = numel(txt);
                end

                body = txt(bodyStart:bodyEnd);

                rows = regexp( ...
                    body, ...
                    ['(?m)^\s*\d+\s+' ...
                     '([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+' ...
                     '([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s*$'], ...
                    'tokens');

                if isempty(rows)
                    continue
                end

                dose = zeros(numel(rows),1);
                vol = zeros(numel(rows),1);

                for j = 1:numel(rows)
                    dose(j) = str2double(rows{j}{1}) * doseScale;
                    vol(j) = str2double(rows{j}{2});
                end

                valid = isfinite(dose) & isfinite(vol);
                dose = dose(valid);
                vol = vol(valid);

                if isempty(dose)
                    continue
                end

                rois(end+1).Name = string(roiName); %#ok<AGROW>
                rois(end).DoseGy = dose;
                rois(end).VolumeCC = vol;
            end

            if isempty(rois)
                error('No numeric DVH data could be parsed.');
            end

            parsed.ROIs = rois;
        end


        function value = getHeaderValue(app,txt,key) %#ok<INUSD>
            pattern = ['(?m)^\s*' regexptranslate('escape',key) ':\s*(.*?)\s*$'];
            tok = regexp(txt,pattern,'tokens','once');

            if isempty(tok)
                value = '';
            else
                value = strtrim(tok{1});
            end
        end


        function metrics = calculateAllMetrics(app,parsed)

            metrics = struct();

            for i = 1:numel(parsed.ROIs)

                roi = parsed.ROIs(i);
                key = app.structureKey(roi.Name);

                if key == ""
                    continue
                end

                totalCC = max(roi.VolumeCC);

                switch key
                    case "gtvres"
                        metrics.gtvres_volume = totalCC;
                        metrics.gtvres_D98 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,totalCC*0.98);

                    case "ctvhr"
                        metrics.ctvhr_volume = totalCC;
                        metrics.ctvhr_D98 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,totalCC*0.98);
                        metrics.ctvhr_D90 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,totalCC*0.90);
                        metrics.ctvhr_D50 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,totalCC*0.50);

                    case "ctvir"
                        metrics.ctvir_volume = totalCC;
                        metrics.ctvir_D98 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,totalCC*0.98);
                        metrics.ctvir_D90 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,totalCC*0.90);

                    case "bladder"
                        metrics.bladder_volume = totalCC;
                        metrics.bladder_D0p1 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,0.1);
                        metrics.bladder_D2 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,2.0);

                    case "rectum"
                        metrics.rectum_volume = totalCC;
                        metrics.rectum_D0p1 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,0.1);
                        metrics.rectum_D2 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,2.0);

                    case "sigmoid"
                        metrics.sigmoid_volume = totalCC;
                        metrics.sigmoid_D0p1 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,0.1);
                        metrics.sigmoid_D2 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,2.0);

                    case "bowel"
                        metrics.bowel_volume = totalCC;
                        metrics.bowel_D0p1 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,0.1);
                        metrics.bowel_D2 = app.doseAtVolume( ...
                            roi.DoseGy,roi.VolumeCC,2.0);
                end
            end

            if isempty(fieldnames(metrics))
                error('No recognized EMBRACE-2 structures were found in the DVH.');
            end
        end


        function key = structureKey(app,roiName) %#ok<INUSD>

            n = lower(strtrim(string(roiName)));
            n = regexprep(n,'[ _-]*fx[1-6]\s*$','');
            n = regexprep(n,'[^a-z0-9]+','');

            if contains(n,'gtvres')
                key = "gtvres";
            elseif contains(n,'ctvhr')
                key = "ctvhr";
            elseif contains(n,'ctvir')
                key = "ctvir";
            elseif contains(n,'bladder')
                key = "bladder";
            elseif contains(n,'rectum')
                key = "rectum";
            elseif contains(n,'sigmoid')
                key = "sigmoid";
            elseif contains(n,'bowel') || contains(n,'intestin')
                key = "bowel";
            else
                key = "";
            end
        end


        function dose = doseAtVolume(app,doseGy,volumeCC,targetCC) %#ok<INUSD>

            doseGy = doseGy(:);
            volumeCC = volumeCC(:);

            valid = isfinite(doseGy) & isfinite(volumeCC);
            doseGy = doseGy(valid);
            volumeCC = volumeCC(valid);

            if isempty(doseGy)
                dose = NaN;
                return
            end

            [doseGy,idx] = sort(doseGy,'ascend');
            volumeCC = volumeCC(idx);

            dose = NaN;

            for i = 1:numel(doseGy)-1
                v1 = volumeCC(i);
                v2 = volumeCC(i+1);

                if (v1 >= targetCC && targetCC >= v2) || ...
                   (v1 <= targetCC && targetCC <= v2)

                    d1 = doseGy(i);
                    d2 = doseGy(i+1);

                    if abs(v2-v1) < eps
                        dose = d1;
                    else
                        f = (targetCC-v1)/(v2-v1);
                        dose = d1 + f*(d2-d1);
                    end
                    return
                end
            end

            [~,nearest] = min(abs(volumeCC-targetCC));
            dose = doseGy(nearest);
        end



        function data = makePriorRTTable(app)
            data = {
                'Dose per fraction [Gy]',           app.fmt(1.8), '', ''
                'Fractions without central shield', app.fmt(25),  '', ''
                'Total dose [Gy]',                  '',           '', ''
                };
        end


        function priorRTEdit(app,source,event)
            row = event.Indices(1);
            col = event.Indices(2);

            if col ~= 2 || row > 2
                data = source.Data;
                data{row,col} = event.PreviousData;
                source.Data = data;
                return
            end

            value = app.toNumber(event.NewData);

            if isnan(value) || value < 0
                data = source.Data;
                data{row,col} = event.PreviousData;
                source.Data = data;
                return
            end

            if row == 2
                value = round(value);
            end

            data = source.Data;
            data{row,col} = app.fmt(value);
            source.Data = data;

            app.recalculateAll();
        end


        function [dosePerFx,nFractions,totalDose,tumourEQD2,oarEQD2] = priorRTValues(app)
            data = app.PriorRTTable.Data;

            dosePerFx = app.toNumber(data{1,2});
            nFractions = app.toNumber(data{2,2});

            if isnan(dosePerFx), dosePerFx = 0; end
            if isnan(nFractions), nFractions = 0; end

            totalDose = dosePerFx * nFractions;
            tumourEQD2 = nFractions * app.eqd2Contribution(dosePerFx,10);
            oarEQD2 = nFractions * app.eqd2Contribution(dosePerFx,3);
        end


        function updatePriorRTDisplay(app)
            [~,~,totalDose,tumourEQD2,oarEQD2] = app.priorRTValues();

            data = app.PriorRTTable.Data;
            data{1,3} = '';
            data{1,4} = '';
            data{2,3} = app.fmt(tumourEQD2);
            data{2,4} = app.fmt(oarEQD2);
            data{3,2} = app.fmt(totalDose);
            data{3,3} = app.fmt(tumourEQD2);
            data{3,4} = app.fmt(oarEQD2);
            app.PriorRTTable.Data = data;
        end


        function baseline = priorRTEQD2(app,alphaBeta)
            [dosePerFx,nFractions,~,tumourEQD2,oarEQD2] = app.priorRTValues();

            if alphaBeta == 10
                baseline = tumourEQD2;
            elseif alphaBeta == 3
                baseline = oarEQD2;
            else
                baseline = nFractions * app.eqd2Contribution(dosePerFx,alphaBeta);
            end
        end


        function tableEdit(app,source,event)

            if isequal(source,app.TargetTable)
                defs = app.TargetDefs;
            else
                defs = app.OARDefs;
            end

            row = event.Indices(1);
            col = event.Indices(2);
            rowType = string(defs{row,2});

            if col < 2 || col > 5
                return
            end

            % Only section rows with a mapped target volume and physical rows
            % can be manually edited.
            editable = (rowType == "physical") || ...
                (rowType == "section" && strlength(string(defs{row,3})) > 0);

            if ~editable
                data = source.Data;
                data{row,col} = event.PreviousData;
                source.Data = data;
                return
            end

            val = app.toNumber(event.NewData);

            if isnan(val)
                data = source.Data;
                if isempty(event.NewData) || strlength(string(event.NewData))==0
                    data{row,col} = '';
                else
                    data{row,col} = event.PreviousData;
                end
                source.Data = data;
            else
                data = source.Data;
                data{row,col} = app.fmt(val);
                source.Data = data;
            end

            app.recalculateAll();
        end


        function recalculateAll(app)
            app.updatePriorRTDisplay();
            app.recalculateTable(app.TargetTable,app.TargetDefs,true);
            app.recalculateTable(app.OARTable,app.OARDefs,false);
        end


        function recalculateTable(app,tableHandle,defs,isTarget)

            data = tableHandle.Data;

            for r = 1:size(defs,1)

                rowType = string(defs{r,2});

                if rowType ~= "eqd"
                    data{r,6} = '';
                    continue
                end

                sourceKey = string(defs{r,4});
                alphaBeta = defs{r,6};
                ebrt = app.priorRTEQD2(alphaBeta);

                sourceRow = app.findRowByKey(defs,sourceKey);

                btSum = 0;
                haveAny = false;

                for fx = 1:4
                    d = app.toNumber(data{sourceRow,fx+1});

                    if isnan(d)
                        data{r,fx+1} = '';
                    else
                        eqd = app.eqd2Contribution(d,alphaBeta);
                        data{r,fx+1} = app.fmt(eqd);
                        btSum = btSum + eqd;
                        haveAny = true;
                    end
                end

                if haveAny
                    total = btSum + ebrt;
                    data{r,6} = app.fmt(total);
                else
                    data{r,6} = '';
                end
            end

            tableHandle.Data = data;
            app.applyTableStyles(tableHandle,defs,isTarget);
        end


        function row = findRowByKey(app,defs,key) %#ok<INUSD>
            row = NaN;

            for r = 1:size(defs,1)
                if string(defs{r,3}) == key
                    row = r;
                    return
                end
            end

            error("Metric mapping not found: " + key);
        end


        function eqd = eqd2Contribution(app,dose,alphaBeta) %#ok<INUSD>
            eqd = dose .* (1 + dose./alphaBeta) ./ ...
                (1 + 2./alphaBeta);
        end


        function s = fmt(app,x) %#ok<INUSD>
            if isempty(x) || ~isfinite(x)
                s = '';
            else
                s = sprintf('%.2f',x);
            end
        end


        function x = toNumber(app,v) %#ok<INUSD>
            if isempty(v)
                x = NaN;
            elseif isnumeric(v)
                if isscalar(v) && isfinite(v)
                    x = double(v);
                else
                    x = NaN;
                end
            else
                x = str2double(string(v));
                if ~isfinite(x)
                    x = NaN;
                end
            end
        end


        function applyTableStyles(app,tableHandle,defs,isTarget) %#ok<INUSD>

            try
                removeStyle(tableHandle);
            catch
            end

            % Center all data/constraint columns. Keep the nomenclature
            % column left-aligned so it reads like the Excel worksheet.
            centerStyle = uistyle('HorizontalAlignment','center');
            for c = 2:8
                addStyle(tableHandle,centerStyle,'column',c);
            end

            leftStyle = uistyle('HorizontalAlignment','left');
            addStyle(tableHandle,leftStyle,'column',1);

            % Match the source workbook:
            %   physical/current dose rows = light blue
            %   calculated EQD2 rows       = white
            %   structure header rows      = light blue and bold
            for r = 1:size(defs,1)

                rowType = string(defs{r,2});

                if rowType == "spacer"
                    st = uistyle( ...
                        'BackgroundColor',[1 1 1], ...
                        'FontColor',[1 1 1]);
                    addStyle(tableHandle,st,'row',r);

                elseif rowType == "section"
                    st = uistyle( ...
                        'BackgroundColor',app.HeaderBlue, ...
                        'FontColor',[0 0 0], ...
                        'FontWeight','bold');
                    addStyle(tableHandle,st,'row',r);

                elseif rowType == "physical"
                    st = uistyle( ...
                        'BackgroundColor',app.CurrentDoseBlue, ...
                        'FontColor',[0 0 0]);
                    addStyle(tableHandle,st,'row',r);

                elseif rowType == "eqd"
                    st = uistyle( ...
                        'BackgroundColor',app.EQDWhite, ...
                        'FontColor',[0 0 0]);
                    addStyle(tableHandle,st,'row',r);
                end
            end

            % The two reference columns are narrow white cells with left-aligned text.
            constraintStyle = uistyle( ...
                'BackgroundColor',app.ConstraintWhite, ...
                'FontColor',[0 0 0], ...
                'HorizontalAlignment','left');

            addStyle(tableHandle,constraintStyle,'column',7);
            addStyle(tableHandle,constraintStyle,'column',8);

            % TOTAL column stays white unless a constraint applies.
            totalStyle = uistyle( ...
                'BackgroundColor',app.EQDWhite, ...
                'FontColor',[0 0 0], ...
                'HorizontalAlignment','center', ...
                'FontWeight','bold');
            addStyle(tableHandle,totalStyle,'column',6);

            % Color only constrained TOTAL EQD2 cells:
            % green  = meets preferred/soft goal
            % yellow = misses preferred goal but meets hard/tolerance
            % red    = fails hard/tolerance
            data = tableHandle.Data;

            for r = 1:size(defs,1)

                if string(defs{r,2}) ~= "eqd"
                    continue
                end

                total = app.toNumber(data{r,6});
                goalText = string(defs{r,8});
                hardText = string(defs{r,9});

                if isnan(total) || ...
                        (strlength(goalText)==0 && strlength(hardText)==0)
                    continue
                end

                [goalMet,goalDefined] = ...
                    app.meetsConstraint(total,goalText,isTarget);
                [hardMet,hardDefined] = ...
                    app.meetsConstraint(total,hardText,isTarget);

                if goalDefined && goalMet
                    bg = app.PassGreen;

                elseif hardDefined && hardMet
                    bg = app.WarnYellow;

                elseif hardDefined && ~hardMet
                    bg = app.FailRed;

                elseif goalDefined && ~goalMet
                    bg = app.FailRed;

                else
                    continue
                end

                st = uistyle( ...
                    'BackgroundColor',bg, ...
                    'FontColor',[0 0 0], ...
                    'HorizontalAlignment','center', ...
                    'FontWeight','bold');

                addStyle(tableHandle,st,'cell',[r 6]);
            end
        end


        function [met,defined] = meetsConstraint(app,value,textValue,isTarget) %#ok<INUSD>

            t = strtrim(string(textValue));
            defined = strlength(t) > 0;
            met = false;

            if ~defined
                return
            end

            % Range, e.g. 90-95.
            tok = regexp(char(t), ...
                '^\s*([0-9.]+)\s*-\s*([0-9.]+)\s*$', ...
                'tokens','once');

            if ~isempty(tok)
                lo = str2double(tok{1});
                hi = str2double(tok{2});
                met = value >= lo && value <= hi;
                return
            end

            tok = regexp(char(t), ...
                '^\s*([<>]=?)\s*([0-9.]+)\s*$', ...
                'tokens','once');

            if isempty(tok)
                return
            end

            op = tok{1};
            threshold = str2double(tok{2});

            switch op
                case '>'
                    met = value > threshold;
                case '>='
                    met = value >= threshold;
                case '<'
                    met = value < threshold;
                case '<='
                    met = value <= threshold;
            end
        end


        function refreshFileStatus(app)

            parts = strings(1,4);

            for fx = 1:4
                if strlength(app.LoadedFiles(fx)) == 0
                    parts(fx) = "Fx" + fx + ": —";
                else
                    parts(fx) = "Fx" + fx + ": " + app.LoadedFiles(fx);
                end
            end

            app.FileStatusLabel.Text = strjoin(parts,"   |   ");
        end


        function clearAll(app,~)

            answer = uiconfirm( ...
                app.UIFigure, ...
                'Clear all Fx1-Fx4 values?', ...
                'Clear Dashboard', ...
                'Options',{'Clear','Cancel'}, ...
                'DefaultOption','Cancel', ...
                'CancelOption','Cancel');

            if ~strcmp(answer,'Clear')
                return
            end

            app.PriorRTTable.Data = app.makePriorRTTable();
            app.TargetTable.Data = app.makeInitialTable(app.TargetDefs);
            app.OARTable.Data = app.makeInitialTable(app.OARDefs);
            app.LoadedFiles(:) = "";
            app.ExplicitlyLoaded(:) = false;
            app.PlanNames(:) = "";
            app.PatientName = "";
            app.PatientID = "";

            app.updatePatientLabel();
            app.updatePlanStatus();
            app.refreshFileStatus();
            app.recalculateAll();

            app.StatusLabel.Text = 'Dashboard cleared.';
        end


        function exportDisplay(app,~)

            try
                templatePath = app.findTemplate();

                defaultBase = "EMBRACE2_EQD2";
                firstLoaded = find(strlength(app.LoadedFiles)>0,1,'first');

                if ~isempty(firstLoaded)
                    raw = regexprep(char(app.LoadedFiles(firstLoaded)), ...
                        '\s+\(carried(?: from Fx\d+)?\)$','');
                    [~,b,~] = fileparts(raw);
                    defaultBase = string(b);
                end

                [file,folder] = uiputfile( ...
                    {'*.xlsx','Excel Workbook (*.xlsx)'}, ...
                    'Export EMBRACE-2 EQD2 Workbook', ...
                    char(defaultBase + ".xlsx"));

                if isequal(file,0)
                    return
                end

                outputPath = fullfile(folder,file);

                [ok,msg] = copyfile(templatePath,outputPath,'f');

                if ~ok
                    error("Could not create output workbook." + newline + string(msg));
                end

                updates = struct();
                updates = app.collectPriorRTUpdates(updates);
                updates = app.collectUpdates(app.TargetTable,app.TargetDefs,updates);
                updates = app.collectUpdates(app.OARTable,app.OARDefs,updates);

                if isempty(fieldnames(updates))
                    delete(outputPath);
                    error('There are no Fx1-Fx4 values to export.');
                end

                updatedSheets = app.writeWorkbook(outputPath,updates);

                app.StatusLabel.Text = "Exported: " + string(outputPath);

                uialert(app.UIFigure, ...
                    sprintf(['Workbook exported successfully.\n\n' ...
                    'Updated sheets:\n%s\n\nSaved to:\n%s'], ...
                    strjoin(updatedSheets,newline),outputPath), ...
                    'Export Complete','Icon','success');

            catch ME
                uialert(app.UIFigure,ME.message, ...
                    'Excel Export Error','Icon','error');
            end
        end



        function updates = collectPriorRTUpdates(app,updates)
            % Existing workbook formulas use:
            % C6 = dose per fraction
            % C7 = fractions without central shield
            data = app.PriorRTTable.Data;

            dosePerFx = app.toNumber(data{1,2});
            nFractions = app.toNumber(data{2,2});

            if ~isnan(dosePerFx)
                updates.C6 = dosePerFx;
            end
            if ~isnan(nFractions)
                updates.C7 = nFractions;
            end
        end


        function updates = collectUpdates(app,tableHandle,defs,updates)

            data = tableHandle.Data;
            excelCols = {'C','D','E','F'};

            for r = 1:size(defs,1)

                rowType = string(defs{r,2});
                excelRow = defs{r,5};
                key = string(defs{r,3});

                % Physical rows include both dose metrics and per-fraction
                % ROI volumes, all of which map back to the template.
                if rowType ~= "physical" || isnan(excelRow) || strlength(key)==0
                    continue
                end

                for fx = 1:4
                    value = app.toNumber(data{r,fx+1});

                    if ~isnan(value)
                        ref = [excelCols{fx} num2str(excelRow)];
                        updates.(ref) = value;
                    end
                end
            end
        end


        function templatePath = findTemplate(app)

            templateName = 'EQD2_with_tolerances_090126.xlsx';
            candidates = strings(0,1);

            p = which(templateName);
            if ~isempty(p)
                candidates(end+1) = string(p);
            end

            classFile = which(class(app));
            if ~isempty(classFile)
                candidates(end+1) = string(fullfile( ...
                    fileparts(classFile),templateName));
            end

            candidates(end+1) = string(fullfile(pwd,templateName));
            candidates = unique(candidates,'stable');

            for i = 1:numel(candidates)
                if isfile(candidates(i))
                    [status,attr] = fileattrib(char(candidates(i)));

                    if status
                        templatePath = attr.Name;
                    else
                        templatePath = char(candidates(i));
                    end
                    return
                end
            end

            error("Could not find " + templateName + "." + newline + ...
                "Keep it beside this MATLAB app or on the MATLAB path.");
        end


        function updatedSheets = writeWorkbook(app,outputPath,updates)

            allSheets = string(sheetnames(outputPath));
            targetSheets = allSheets(contains(upper(allSheets),"FX1-4"));

            if isempty(targetSheets)
                error('No worksheet containing "FX1-4" was found.');
            end

            refs = fieldnames(updates);

            if ispc
                excel = [];
                workbook = [];

                try
                    [status,attr] = fileattrib(outputPath);

                    if status
                        fullPath = attr.Name;
                    else
                        fullPath = outputPath;
                    end

                    excel = actxserver('Excel.Application');
                    excel.Visible = false;
                    excel.DisplayAlerts = false;

                    workbook = excel.Workbooks.Open(char(fullPath));

                    for s = 1:numel(targetSheets)
                        ws = workbook.Worksheets.Item(char(targetSheets(s)));

                        for i = 1:numel(refs)
                            ws.Range(refs{i}).Value = updates.(refs{i});
                        end
                    end

                    excel.CalculateFullRebuild;
                    workbook.Save;
                    workbook.Close(false);

                    excel.Quit;
                    delete(excel);

                    updatedSheets = targetSheets;
                    return

                catch ME
                    try
                        if ~isempty(workbook)
                            workbook.Close(false);
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

                    warning("Excel automation failed: %s",ME.message);
                end
            end

            for s = 1:numel(targetSheets)
                for i = 1:numel(refs)
                    writematrix( ...
                        updates.(refs{i}), ...
                        outputPath, ...
                        'Sheet',char(targetSheets(s)), ...
                        'Range',refs{i});
                end
            end

            updatedSheets = targetSheets;
        end


        function configureTable(app,tbl,columnNames)

            tbl.ColumnName = columnNames;
            tbl.ColumnWidth = {245,82,82,82,82,120,105,105};
            tbl.ColumnEditable = [false true true true true false false false];
            tbl.RowName = {};
            tbl.FontName = 'Arial';
            tbl.FontSize = 11;
            tbl.ForegroundColor = [0 0 0];
            tbl.BackgroundColor = [1 1 1];
            tbl.CellEditCallback = @(s,e)app.tableEdit(s,e);
        end


        function createComponents(app)

            app.initializeDefinitions();

            app.UIFigure = uifigure('Visible','off');
            app.UIFigure.Name = 'EMBRACE-2 EQD2 Excel Autogenerator';
            app.UIFigure.Position = [70 20 1055 980];
            app.UIFigure.Color = app.Black;

            app.MainGrid = uigridlayout(app.UIFigure,[9 1]);
            app.MainGrid.BackgroundColor = app.Black;
            app.MainGrid.RowHeight = {52,102,26,105,26,290,26,'1x',60};
            app.MainGrid.RowSpacing = 6;
            app.MainGrid.Padding = [12 8 12 8];

            %% Header
            app.HeaderPanel = uipanel(app.MainGrid);
            app.HeaderPanel.Layout.Row = 1;
            app.HeaderPanel.BackgroundColor = app.Black;
            app.HeaderPanel.BorderType = 'none';

            app.HeaderGrid = uigridlayout(app.HeaderPanel,[1 2]);
            app.HeaderGrid.BackgroundColor = app.Black;
            app.HeaderGrid.ColumnWidth = {'1x',170};
            app.HeaderGrid.Padding = [0 0 0 0];

            app.TitleLabel = uilabel(app.HeaderGrid);
            app.TitleLabel.Text = 'EMBRACE-2  EQD2 Excel Autogenerator';
            app.TitleLabel.FontSize = 22;
            app.TitleLabel.FontWeight = 'bold';
            app.TitleLabel.FontColor = app.White;

            app.BrandLabel = uilabel(app.HeaderGrid);
            app.BrandLabel.Text = 'UFHPTI';
            app.BrandLabel.FontSize = 11;
            app.BrandLabel.FontWeight = 'bold';
            app.BrandLabel.FontColor = app.UFOrange;
            app.BrandLabel.HorizontalAlignment = 'right';

            %% Compact equal-width load buttons
            app.LoadPanel = uipanel(app.MainGrid);
            app.LoadPanel.Layout.Row = 2;
            app.LoadPanel.BackgroundColor = app.NearBlack;
            app.LoadPanel.BorderColor = [0.18 0.18 0.20];

            app.LoadGrid = uigridlayout(app.LoadPanel,[3 6]);
            app.LoadGrid.BackgroundColor = app.NearBlack;
            app.LoadGrid.RowHeight = {34,22,22};
            app.LoadGrid.ColumnWidth = {300,115,115,115,115,'1x'};
            app.LoadGrid.ColumnSpacing = 8;
            app.LoadGrid.Padding = [10 6 10 5];

            app.LoadLabel = uilabel(app.LoadGrid);
            app.LoadLabel.Text = 'Patient: —    |    Patient ID: —';
            app.LoadLabel.FontWeight = 'bold';
            app.LoadLabel.FontColor = app.White;
            app.LoadLabel.Layout.Row = 1;
            app.LoadLabel.Layout.Column = 1;

            app.Fx1Button = uibutton(app.LoadGrid,'push');
            app.Fx1Button.Text = 'Load F1';
            app.Fx1Button.FontWeight = 'bold';
            app.Fx1Button.BackgroundColor = app.UFBlue;
            app.Fx1Button.FontColor = app.White;
            app.Fx1Button.ButtonPushedFcn = @(s,e)app.loadFraction(1);
            app.Fx1Button.Layout.Row = 1;
            app.Fx1Button.Layout.Column = 2;

            app.Fx2Button = uibutton(app.LoadGrid,'push');
            app.Fx2Button.Text = 'Load F2';
            app.Fx2Button.FontWeight = 'bold';
            app.Fx2Button.BackgroundColor = app.UFBlue;
            app.Fx2Button.FontColor = app.White;
            app.Fx2Button.ButtonPushedFcn = @(s,e)app.loadFraction(2);
            app.Fx2Button.Layout.Row = 1;
            app.Fx2Button.Layout.Column = 3;

            app.Fx3Button = uibutton(app.LoadGrid,'push');
            app.Fx3Button.Text = 'Load F3';
            app.Fx3Button.FontWeight = 'bold';
            app.Fx3Button.BackgroundColor = app.UFBlue;
            app.Fx3Button.FontColor = app.White;
            app.Fx3Button.ButtonPushedFcn = @(s,e)app.loadFraction(3);
            app.Fx3Button.Layout.Row = 1;
            app.Fx3Button.Layout.Column = 4;

            app.Fx4Button = uibutton(app.LoadGrid,'push');
            app.Fx4Button.Text = 'Load F4';
            app.Fx4Button.FontWeight = 'bold';
            app.Fx4Button.BackgroundColor = app.UFBlue;
            app.Fx4Button.FontColor = app.White;
            app.Fx4Button.ButtonPushedFcn = @(s,e)app.loadFraction(4);
            app.Fx4Button.Layout.Row = 1;
            app.Fx4Button.Layout.Column = 5;

            app.PlanStatusLabel = uilabel(app.LoadGrid);
            app.PlanStatusLabel.Text = 'F1 Plan: —    |    F2 Plan: —    |    F3 Plan: —    |    F4 Plan: —';
            app.PlanStatusLabel.FontSize = 9;
            app.PlanStatusLabel.FontWeight = 'bold';
            app.PlanStatusLabel.FontColor = app.White;
            app.PlanStatusLabel.Layout.Row = 2;
            app.PlanStatusLabel.Layout.Column = [1 6];

            app.FileStatusLabel = uilabel(app.LoadGrid);
            app.FileStatusLabel.FontSize = 9;
            app.FileStatusLabel.FontColor = app.Muted;
            app.FileStatusLabel.Layout.Row = 3;
            app.FileStatusLabel.Layout.Column = [1 6];

            %% Prior RT / EBRT fractionation
            app.PriorRTHeader = uilabel(app.MainGrid);
            app.PriorRTHeader.Layout.Row = 3;
            app.PriorRTHeader.Text = 'PRIOR RT / EBRT FRACTIONATION';
            app.PriorRTHeader.FontSize = 14;
            app.PriorRTHeader.FontWeight = 'bold';
            app.PriorRTHeader.FontColor = app.White;

            app.PriorRTTable = uitable(app.MainGrid);
            app.PriorRTTable.Layout.Row = 4;
            app.PriorRTTable.Data = app.makePriorRTTable();
            app.PriorRTTable.ColumnName = { ...
                'Parameter', ...
                'Value', ...
                'EQD2 [Gy] (alpha/beta = 10)', ...
                'EQD2 [Gy] (alpha/beta = 3)'};
            app.PriorRTTable.ColumnWidth = {300,130,190,190};
            app.PriorRTTable.ColumnEditable = [false true false false];
            app.PriorRTTable.RowName = {};
            app.PriorRTTable.FontName = 'Arial';
            app.PriorRTTable.FontSize = 11;
            app.PriorRTTable.ForegroundColor = [0 0 0];
            app.PriorRTTable.BackgroundColor = [1 1 1];
            app.PriorRTTable.CellEditCallback = @(s,e)app.priorRTEdit(s,e);

            inputStyle = uistyle( ...
                'BackgroundColor',app.CurrentDoseBlue, ...
                'FontColor',[0 0 0], ...
                'HorizontalAlignment','center');
            addStyle(app.PriorRTTable,inputStyle,'cell',[1 2]);
            addStyle(app.PriorRTTable,inputStyle,'cell',[2 2]);

            centerPriorStyle = uistyle('HorizontalAlignment','center');
            addStyle(app.PriorRTTable,centerPriorStyle,'column',2);
            addStyle(app.PriorRTTable,centerPriorStyle,'column',3);
            addStyle(app.PriorRTTable,centerPriorStyle,'column',4);

            %% Target section
            app.TargetHeader = uilabel(app.MainGrid);
            app.TargetHeader.Layout.Row = 5;
            app.TargetHeader.Text = 'TARGETS';
            app.TargetHeader.FontSize = 14;
            app.TargetHeader.FontWeight = 'bold';
            app.TargetHeader.FontColor = app.White;

            app.TargetTable = uitable(app.MainGrid);
            app.TargetTable.Layout.Row = 6;
            app.TargetTable.Data = app.makeInitialTable(app.TargetDefs);

            app.configureTable(app.TargetTable,{ ...
                'Structure / Dose Parameter [units]', ...
                'F1','F2','F3','F4', ...
                'TOTAL BT + EBT', ...
                'Planning Goal', ...
                'Tolerance'});

            %% OAR section
            app.OARHeader = uilabel(app.MainGrid);
            app.OARHeader.Layout.Row = 7;
            app.OARHeader.Text = 'ORGANS AT RISK';
            app.OARHeader.FontSize = 14;
            app.OARHeader.FontWeight = 'bold';
            app.OARHeader.FontColor = app.White;

            app.OARTable = uitable(app.MainGrid);
            app.OARTable.Layout.Row = 8;
            app.OARTable.Data = app.makeInitialTable(app.OARDefs);

            app.configureTable(app.OARTable,{ ...
                'Structure / Dose Parameter [units]', ...
                'F1','F2','F3','F4', ...
                'TOTAL BT + EBT', ...
                'Soft Constraints', ...
                'Hard Constraints'});

            %% Footer
            app.FooterPanel = uipanel(app.MainGrid);
            app.FooterPanel.Layout.Row = 9;
            app.FooterPanel.BackgroundColor = app.Black;
            app.FooterPanel.BorderType = 'none';

            app.FooterGrid = uigridlayout(app.FooterPanel,[1 3]);
            app.FooterGrid.BackgroundColor = app.Black;
            app.FooterGrid.ColumnWidth = {'1x',110,285};
            app.FooterGrid.ColumnSpacing = 10;
            app.FooterGrid.Padding = [0 6 0 2];

            app.StatusLabel = uilabel(app.FooterGrid);
            app.StatusLabel.Text = 'Ready';
            app.StatusLabel.FontSize = 10;
            app.StatusLabel.FontColor = app.Muted;

            app.ClearButton = uibutton(app.FooterGrid,'push');
            app.ClearButton.Text = 'Clear All';
            app.ClearButton.ButtonPushedFcn = @(s,e)app.clearAll(e);

            app.ExportButton = uibutton(app.FooterGrid,'push');
            app.ExportButton.Text = 'EXPORT CURRENT DISPLAY TO EXCEL';
            app.ExportButton.FontWeight = 'bold';
            app.ExportButton.FontColor = app.White;
            app.ExportButton.BackgroundColor = app.UFOrange;
            app.ExportButton.ButtonPushedFcn = @(s,e)app.exportDisplay(e);

            app.UIFigure.Visible = 'on';
        end
    end


    methods (Access = public)

        function app = EMBRACE2_EQD2_Excel_Autogenerator

            app.createComponents();
            registerApp(app,app.UIFigure);
            runStartupFcn(app,@startupFcn);

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
