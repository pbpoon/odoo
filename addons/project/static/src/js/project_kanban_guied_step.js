odoo.define('project.guied_step', function (require) {
'use strict';

var core = require('web.core');
var _t = core._t;
var Registry = require('web.KanbanView_registry');

Registry.add('project',{
helpStages: [{
    placeholder:_t('ToDo'),
    records: 3
},{
    placeholder:_t('In Progress'),
    records: 4
},{
    placeholder:_t('Done'),
    records: 2
}],
exampleStages: [{
    title: _t('Software Development'),
    stages: [_t('Backlog'), _t('Specifications'), _t('Development'), _t('Tests'), _t('Delivered')],
    footnote: _t('Once a task is specified, set it <span class="o_status o_status_green"></span> in the Specifications column, so that developers know they can pull it. If you work in sprints, use <a style="color:gold;" class="o_priority_star fa fa-star"/> to mark tasks of the current sprint.'),
},{
    title: _t('Agile'),
    stages: [_t('Backlog'), _t('Analysis'), _t('Development'), _t('Testing'), _t('Done')],
    footnote: _t('Waiting for the next stage : use <span class="o_status o_status_green"></span> / <span class="o_status o_status_red"></span> bullet'),
},{
    title: _t('Digital Marketing'),
    stages: [_t('Ideas'), _t('Researching'), _t('Writing'), _t('Editing'), _t('Done')],
    footnote: _t('Everyone can propose ideas, and the Editor mark the best ones as <span class="o_status o_status_green"></span> . Attach all documents or links to the task directly, to have all information about a research centralized.'),
},{
    title: _t('Customer Feedback'),
    stages: [_t('New'), _t('In development'), _t('Done'), _t('Refused')],
    footnote: _t('Customers propose feedbacks by email; Odoo creates tasks automatically, and you can communicate on the task directly. Your managers decide which feedback is accepted <span class="o_status o_status_green"></span> and which feedback is moved to the Refused column.'),
},{
    title: _t('Getting Things Done (GTD)'),
    stages: [_t('Inbox'), _t('Today'), _t('This Week'), _t('This Month'), _t('Long Term')],
    footnote: _t('Fill your Inbox easily with the email gateway. Periodically review your Inbox and schedule tasks by moving them to others columns. Every day, you review the "This Week" column to move important tasks Today. Every Monday, you review the This Month column.'),
},{
    title: _t('Consulting'),
    stages: [_t('New Projects'), _t('Resources Allocation'), _t('In Progress'), _t('Done')],
},{
    title: _t('Research Project'),
    stages: [_t('Brainstorm'), _t('Research'), _t('Draft'), _t('Final Document')],
},{
    title: _t('Website Redesign'),
    stages: [_t('Page Ideas'), _t('Copywriting'), _t('Design'), _t('Live')],
},{
    title: _t('T-shirt Printing'),
    stages: [_t('New Orders'), _t('Logo Design'), _t('To Print'), _t('Done')],
    footnote: _t('Communicate with customers on the task using the email gateway. Attach logo designs to the task, so that information flow from designers to the workers who print the t-shirt. Organize priorities amongst orders <a style="color:gold;" class="o_priority_star fa fa-star"/> using the icon.'),
}]});
});
